"""Hybrid retrieval: prefetch dense + BM25 → RRF trong một request, kèm nhánh dense lấy `max_cosine` (§10.4)."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from langchain_core.embeddings import Embeddings
from qdrant_client import AsyncQdrantClient, models

from ai_service.rag import sparse
from ai_service.rag.qdrant_store import DENSE, SPARSE

PREFETCH_LIMIT = 20
DEFAULT_K = 8


@dataclass(frozen=True)
class RetrievalQuery:
    text: str  # câu gốc (có thể tiếng Việt) → nhánh dense, embedding đa ngôn ngữ
    text_en: str | None = None  # bản tiếng Anh do plan_retrieval sinh → nhánh BM25 (KB tiếng Anh)
    doc_types: list[str] | None = None
    product_id: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_path: str
    title: str
    doc_type: str
    section: str
    content: str
    effective_date: str
    version: int
    score: float  # điểm RRF — chỉ có nghĩa thứ hạng tương đối
    token_count: int = 0
    product_id: str | None = None
    has_clinical_studies: bool = False

    @classmethod
    def from_point(cls, p: models.ScoredPoint) -> "RetrievedChunk":
        pl: dict[str, Any] = p.payload or {}
        return cls(
            chunk_id=pl["chunk_id"],
            source_path=pl["source_path"],
            title=pl["title"],
            doc_type=pl["doc_type"],
            section=pl.get("section", ""),
            content=pl["content"],
            effective_date=pl["effective_date"],
            version=pl.get("version", 1),
            score=p.score,
            token_count=pl.get("token_count", 0),
            product_id=pl.get("product_id"),
            has_clinical_studies=bool(pl.get("has_clinical_studies")),
        )


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    max_cosine: float = 0.0  # cosine tuyệt đối cao nhất — dùng cho ngưỡng abstain


def _filter(q: RetrievalQuery) -> models.Filter:
    must: list[models.Condition] = [models.FieldCondition(key="status", match=models.MatchValue(value="active"))]
    if q.doc_types:
        must.append(models.FieldCondition(key="doc_type", match=models.MatchAny(any=q.doc_types)))
    if q.product_id:
        must.append(models.FieldCondition(key="product_id", match=models.MatchValue(value=q.product_id)))
    return models.Filter(must=must)


class Retriever:
    def __init__(self, qdrant: AsyncQdrantClient, embedder: Embeddings, collection: str) -> None:
        self.qdrant, self.embedder, self.collection = qdrant, embedder, collection

    async def hybrid_search(self, q: RetrievalQuery, k: int = DEFAULT_K) -> RetrievalResult:
        return await self.search_many([q], k=k)

    async def search_many(self, queries: list[RetrievalQuery], k: int = DEFAULT_K) -> RetrievalResult:
        """Nhiều query → MỘT `query_batch_points`; gộp, loại trùng theo point ID (giữ điểm cao nhất)."""
        if not queries:
            return RetrievalResult()
        dense_vecs = await self.embedder.aembed_documents([q.text for q in queries])
        sparse_vecs = await asyncio.to_thread(lambda: [sparse.embed_query(q.text_en or q.text) for q in queries])

        requests: list[models.QueryRequest] = []
        for q, dense, sp in zip(queries, dense_vecs, sparse_vecs, strict=True):
            flt = _filter(q)
            requests += [
                models.QueryRequest(
                    prefetch=[
                        models.Prefetch(query=dense, using=DENSE, filter=flt, limit=PREFETCH_LIMIT),
                        models.Prefetch(query=sp, using=SPARSE, filter=flt, limit=PREFETCH_LIMIT),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    filter=flt,
                    limit=k,
                    with_payload=True,
                ),
                # Nhánh dense riêng: RRF chỉ phản ánh thứ hạng, cosine tuyệt đối mới cho biết KB có thứ liên quan không
                models.QueryRequest(query=dense, using=DENSE, filter=flt, limit=1),
            ]
        responses = await self.qdrant.query_batch_points(self.collection, requests=requests)

        best: dict[str, models.ScoredPoint] = {}
        max_cosine = 0.0
        for hybrid, dense_top in zip(responses[::2], responses[1::2], strict=True):
            for p in hybrid.points:
                pid = str(p.id)
                if pid not in best or p.score > best[pid].score:
                    best[pid] = p
            if dense_top.points:
                max_cosine = max(max_cosine, dense_top.points[0].score)
        ranked = sorted(best.values(), key=lambda p: p.score, reverse=True)[:k]
        return RetrievalResult(chunks=[RetrievedChunk.from_point(p) for p in ranked], max_cosine=max_cosine)
