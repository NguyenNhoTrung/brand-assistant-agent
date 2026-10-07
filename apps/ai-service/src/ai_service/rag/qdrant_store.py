"""Collection Qdrant `kb_chunks`: dense (OpenAI) + sparse BM25, payload index (§10.3)."""

import warnings

from qdrant_client import AsyncQdrantClient, models

from ai_service.llm.config import load_models
from ai_service.rag.ingest.chunker import Chunk
from ai_service.rag.ingest.validator import Document
from ai_service.settings import settings
from shared import kb

DENSE = "dense"
SPARSE = "bm25"


def make_client() -> AsyncQdrantClient:
    with warnings.catch_warnings():  # local/compose: api-key qua http nội bộ là cố ý
        warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
        return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def dense_dims() -> int:
    return load_models(settings.models_file)["embed"].dims or 1536


def point_id(source_path: str, ordinal: int) -> str:
    return kb.point_id(kb.chunk_id(source_path, ordinal))


chunk_id = kb.chunk_id


async def ensure_collection(client: AsyncQdrantClient, collection: str) -> None:
    if await client.collection_exists(collection):
        return
    await client.create_collection(
        collection_name=collection,
        vectors_config={DENSE: models.VectorParams(size=dense_dims(), distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    kw = models.PayloadSchemaType.KEYWORD
    for field, schema in [
        ("doc_type", kw),
        ("status", kw),
        ("source_path", kw),
        ("product_id", kw),
        ("effective_date", models.PayloadSchemaType.DATETIME),
        ("ordinal", models.PayloadSchemaType.INTEGER),
    ]:
        await client.create_payload_index(collection, field_name=field, field_schema=schema, wait=True)


def to_point(
    doc: Document, chunk: Chunk, dense: list[float], sparse: models.SparseVector, *, status: str
) -> models.PointStruct:
    return models.PointStruct(
        id=point_id(doc.source_path, chunk.ordinal),
        vector={DENSE: dense, SPARSE: sparse},
        payload={
            "chunk_id": chunk_id(doc.source_path, chunk.ordinal),
            "source_path": doc.source_path,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "status": status,
            "product_id": doc.meta.get("product_id"),
            "has_clinical_studies": bool(doc.meta.get("clinical_studies")),  # CMP-002
            "effective_date": doc.effective_date.isoformat(),
            "version": doc.version,
            "heading_path": list(chunk.heading_path),
            "section": chunk.section,
            "context_header": chunk.context_header,
            "ordinal": chunk.ordinal,
            "token_count": chunk.token_count,
            "content": chunk.content,
        },
    )


def by_source(source_path: str, *extra: models.Condition) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="source_path", match=models.MatchValue(value=source_path)), *extra]
    )
