"""Định danh chunk trong Qdrant — ai-service ghi (ingest), gateway đọc (hover citation) → một nơi định nghĩa."""

from uuid import UUID, uuid5

NAMESPACE = UUID("6f1c2b1e-4d1a-5b8e-9a51-6b7c0e2d9f10")  # cố định → point ID deterministic


def chunk_id(source_path: str, ordinal: int) -> str:
    return f"{source_path}#{ordinal}"


def point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE, chunk_id))
