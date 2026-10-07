"""BM25 sparse bằng FastEmbed `Qdrant/bm25` — chạy local, deterministic (§10.3).

`embed()` cho tài liệu lúc ingest, `query_embed()` cho câu hỏi. Model tải lần đầu (~MB) rồi cache.
"""

from functools import cache
from typing import TYPE_CHECKING

from qdrant_client import models

if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding

MODEL = "Qdrant/bm25"


@cache
def _model() -> "SparseTextEmbedding":
    from fastembed import SparseTextEmbedding  # extra `rag` — import muộn để worker/test nhẹ khởi động

    return SparseTextEmbedding(MODEL)


def _vec(e) -> models.SparseVector:  # type: ignore[no-untyped-def]
    return models.SparseVector(indices=e.indices.tolist(), values=e.values.tolist())


def embed_documents(texts: list[str]) -> list[models.SparseVector]:
    return [_vec(e) for e in _model().embed(texts)]


def embed_query(text: str) -> models.SparseVector:
    return _vec(next(iter(_model().query_embed(text))))
