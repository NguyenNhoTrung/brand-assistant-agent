"""Ingest vào collection test thật (Qdrant + Redis DB 15 + OpenAI embedding)."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from qdrant_client import models

from ai_service.rag.retriever import RetrievalQuery, Retriever

from .rag_env import RagEnv, copy_kb

pytestmark = [pytest.mark.infra, pytest.mark.llm]

FILES = [
    "products/vitamin-c-serum.md",
    "products/vitamin-c-serum-2025.md",
    "sops/us-shipping-policy.md",
    "compliance/ad-claims-policy.md",
    "brand/brand-voice.md",
]


@pytest.fixture
async def env() -> AsyncIterator[RagEnv]:
    e = RagEnv("kb_chunks_test_ingest")
    await e.drop()
    yield e
    await e.drop()
    await e.close()


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    return copy_kb(tmp_path / "kb", FILES)


async def _points(env: RagEnv, source_path: str | None = None) -> list[models.Record]:
    flt = None
    if source_path:
        flt = models.Filter(must=[models.FieldCondition(key="source_path", match=models.MatchValue(value=source_path))])
    records, _ = await env.qdrant.scroll(env.collection, scroll_filter=flt, limit=1000, with_payload=True)
    return records


async def test_ingest_idempotent_and_counts_match(env: RagEnv, kb: Path) -> None:
    r1, _ = await env.ingest(kb)
    assert sorted(r1.added) == sorted(FILES) and not r1.rejected

    manifest = await env.manifest.all()
    count = (await env.qdrant.count(env.collection, exact=True)).count
    assert count == sum(m.chunk_count for m in manifest.values()) == r1.chunks_written

    r2, emb2 = await env.ingest(kb)
    assert sorted(r2.skipped) == sorted(FILES)
    assert r2.added == r2.updated == r2.deleted == []
    assert emb2.misses == 0
    assert (await env.qdrant.count(env.collection, exact=True)).count == count


async def test_embedding_cache_second_ingest_does_not_call_openai(env: RagEnv, kb: Path) -> None:
    await env.ingest(kb)
    # --recreate xóa collection + manifest → phải embed lại mọi chunk, nhưng tất cả lấy từ cache emb:*
    r2, emb2 = await env.ingest(kb, recreate=True)
    assert sorted(r2.added) == sorted(FILES)
    assert emb2.misses == 0
    assert emb2.hits == r2.chunks_written > 0


async def test_superseded_doc_never_returned(env: RagEnv, kb: Path) -> None:
    await env.ingest(kb)
    old = await _points(env, "products/vitamin-c-serum-2025.md")
    assert old and all(p.payload and p.payload["status"] == "superseded" for p in old)

    retriever = Retriever(env.qdrant, env.embedder(), env.collection)
    res = await retriever.hybrid_search(RetrievalQuery("What was the price of the Vitamin C Serum in 2025? $38"), k=10)
    paths = [c.source_path for c in res.chunks]
    assert paths[0] == "products/vitamin-c-serum.md"
    assert "products/vitamin-c-serum-2025.md" not in paths
    assert all("$38" not in c.content for c in res.chunks)


async def test_doc_type_filter(env: RagEnv, kb: Path) -> None:
    await env.ingest(kb)
    retriever = Retriever(env.qdrant, env.embedder(), env.collection)
    res = await retriever.hybrid_search(RetrievalQuery("vitamin c serum price", doc_types=["sop"]), k=10)
    assert res.chunks and {c.doc_type for c in res.chunks} == {"sop"}
    res = await retriever.hybrid_search(RetrievalQuery("claims", doc_types=["compliance", "brand_guideline"]), k=10)
    assert {c.doc_type for c in res.chunks} == {"compliance", "brand_guideline"}


async def test_deleted_file_removes_points(env: RagEnv, kb: Path) -> None:
    await env.ingest(kb)
    assert await _points(env, "brand/brand-voice.md")

    (kb / "brand" / "brand-voice.md").unlink()
    r, _ = await env.ingest(kb)
    assert r.deleted == ["brand/brand-voice.md"]
    assert await _points(env, "brand/brand-voice.md") == []
    assert "brand/brand-voice.md" not in await env.manifest.all()


async def test_changed_file_reindexed_and_supersedes_removed_reactivates_old(env: RagEnv, kb: Path) -> None:
    await env.ingest(kb)
    new = kb / "products" / "vitamin-c-serum.md"
    new.write_text(new.read_text().replace("supersedes: products/vitamin-c-serum-2025.md\n", ""))

    r, _ = await env.ingest(kb)
    assert r.updated == ["products/vitamin-c-serum.md"]
    assert r.status_changed == ["products/vitamin-c-serum-2025.md"]  # không đổi nội dung, chỉ đổi status
    old = await _points(env, "products/vitamin-c-serum-2025.md")
    assert all(p.payload and p.payload["status"] == "active" for p in old)
    assert (await env.manifest.all())["products/vitamin-c-serum-2025.md"].status == "active"


async def test_invalid_file_rejected_others_ingested(env: RagEnv, kb: Path) -> None:
    (kb / "sops" / "broken.md").write_text("---\ntitle: Broken\neffective_date: someday\n---\n\n## X\n\ny\n")
    r, _ = await env.ingest(kb)
    assert set(r.rejected) == {"sops/broken.md"}
    assert "thiếu `doc_type`" in r.rejected["sops/broken.md"]
    assert len(r.added) == len(FILES)
