"""load → validate → (skip theo content_hash) → chunk → embed dense + BM25 → upsert Qdrant → kb:manifest (§10.2).

- Manifest ghi SAU CÙNG cho mỗi tài liệu → bị ngắt giữa chừng thì lần sau làm lại tài liệu đó.
- Point ID = uuid5(path#ordinal) → upsert đè đúng chỗ; chunk thừa (ordinal ≥ số chunk mới) bị xóa sau.
- File có trong manifest nhưng không còn trên đĩa → xóa point + HDEL.
- `supersedes` tính trên TOÀN BỘ KB mỗi lần chạy → tài liệu cũ (kể cả không đổi) được set status=superseded.
"""

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from langchain_core.embeddings import Embeddings
from qdrant_client import AsyncQdrantClient, models

from ai_service.rag import sparse
from ai_service.rag.ingest.chunker import chunk_document
from ai_service.rag.ingest.loader import FrontmatterError, load_file
from ai_service.rag.ingest.manifest import Manifest, ManifestEntry
from ai_service.rag.ingest.validator import Document, InvalidDocumentError, validate
from ai_service.rag.qdrant_store import by_source, ensure_collection, to_point

log = structlog.get_logger()

# (source_path, action, đã xử lý, tổng) — action: added|updated|skipped|deleted|status_changed
Progress = Callable[[str, str, int, int], Awaitable[None]]


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    status_changed: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    chunks_written: int = 0

    def summary(self) -> str:
        return (
            f"added={len(self.added)} updated={len(self.updated)} skipped={len(self.skipped)} "
            f"deleted={len(self.deleted)} status_changed={len(self.status_changed)} "
            f"rejected={len(self.rejected)} chunks_written={self.chunks_written}"
        )


def load_documents(kb_dir: Path, report: IngestReport) -> list[Document]:
    docs = []
    for path in sorted(kb_dir.rglob("*.md")):
        try:
            docs.append(validate(load_file(path, kb_dir)))
        except (FrontmatterError, InvalidDocumentError, UnicodeDecodeError) as e:
            rel = path.relative_to(kb_dir).as_posix()
            report.rejected[rel] = str(e)
            log.warning("ingest.rejected", source_path=rel, error=str(e))
    return docs


def _superseded(docs: list[Document]) -> set[str]:
    on_disk = {d.source_path for d in docs}
    out = set()
    for d in docs:
        if d.supersedes:
            if d.supersedes in on_disk:
                out.add(d.supersedes)
            else:
                log.warning("ingest.supersedes_missing", source_path=d.source_path, supersedes=d.supersedes)
    return out


async def run_ingest(
    kb_dir: Path,
    *,
    qdrant: AsyncQdrantClient,
    manifest: Manifest,
    embedder: Embeddings,
    collection: str,
    recreate: bool = False,
    on_progress: Progress | None = None,
) -> IngestReport:
    report = IngestReport()
    if recreate:
        await qdrant.delete_collection(collection)
        await manifest.clear()
        log.info("ingest.recreated", collection=collection)
    await ensure_collection(qdrant, collection)

    docs = load_documents(kb_dir, report)
    superseded = _superseded(docs)
    known = await manifest.all()
    gone = sorted(set(known) - ({d.source_path for d in docs} | set(report.rejected)))
    total, done = len(gone) + len(docs), 0

    async def progress(path: str, action: str) -> None:
        nonlocal done
        done += 1
        if on_progress:
            await on_progress(path, action, done, total)

    # File đã bị xóa khỏi KB (file bị reject vẫn còn trên đĩa → giữ index cũ, chỉ cảnh báo)
    for path in gone:
        await qdrant.delete(collection, points_selector=models.FilterSelector(filter=by_source(path)), wait=True)
        await manifest.remove(path)
        report.deleted.append(path)
        log.info("ingest.deleted", source_path=path)
        await progress(path, "deleted")

    for doc in docs:
        status = "superseded" if doc.source_path in superseded else "active"
        prev = known.get(doc.source_path)
        if prev and prev.content_hash == doc.content_hash:
            if prev.status == status:
                report.skipped.append(doc.source_path)
                await progress(doc.source_path, "skipped")
                continue
            await qdrant.set_payload(
                collection, payload={"status": status}, points=by_source(doc.source_path), wait=True
            )
            await manifest.put(doc.source_path, _entry(doc, prev.chunk_count, status))
            report.status_changed.append(doc.source_path)
            log.info("ingest.status_changed", source_path=doc.source_path, status=status)
            await progress(doc.source_path, "status_changed")
            continue

        n = await _index_document(doc, status, qdrant=qdrant, embedder=embedder, collection=collection)
        await manifest.put(doc.source_path, _entry(doc, n, status))
        (report.updated if prev else report.added).append(doc.source_path)
        report.chunks_written += n
        log.info("ingest.indexed", source_path=doc.source_path, chunks=n, status=status)
        await progress(doc.source_path, "updated" if prev else "added")

    log.info("ingest.done", collection=collection, summary=report.summary())
    return report


async def _index_document(
    doc: Document, status: str, *, qdrant: AsyncQdrantClient, embedder: Embeddings, collection: str
) -> int:
    chunks = chunk_document(doc.title, doc.body)
    texts = [c.embed_text for c in chunks]
    dense = await embedder.aembed_documents(texts)
    sparse_vecs = await asyncio.to_thread(sparse.embed_documents, texts)
    points = [to_point(doc, c, d, s, status=status) for c, d, s in zip(chunks, dense, sparse_vecs, strict=True)]
    await qdrant.upsert(collection, points=points, wait=True)
    # Tài liệu ngắn đi → xóa chunk thừa của phiên bản trước
    stale = models.FieldCondition(key="ordinal", range=models.Range(gte=len(chunks)))
    await qdrant.delete(
        collection, points_selector=models.FilterSelector(filter=by_source(doc.source_path, stale)), wait=True
    )
    return len(chunks)


def _entry(doc: Document, chunk_count: int, status: str) -> ManifestEntry:
    return ManifestEntry(
        content_hash=doc.content_hash,
        chunk_count=chunk_count,
        status=status,
        title=doc.title,
        doc_type=doc.doc_type,
        version=doc.version,
        effective_date=doc.effective_date.isoformat(),
        ingested_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    )
