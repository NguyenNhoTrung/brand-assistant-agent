"""Hạ tầng riêng cho test RAG: Redis DB 15 + collection `kb_chunks_test*` — không đụng dữ liệu dev."""

import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from ai_service.llm.client import embeddings
from ai_service.llm.embed_cache import CachedEmbeddings
from ai_service.rag.ingest.manifest import Manifest
from ai_service.rag.ingest.pipeline import IngestReport, run_ingest
from ai_service.rag.qdrant_store import make_client
from ai_service.settings import settings

KB_DIR = Path(__file__).resolve().parents[4] / "data" / "knowledge"
TEST_DB = 15


def redis_db15() -> Redis:
    return Redis.from_url(urlunparse(urlparse(settings.redis_url)._replace(path=f"/{TEST_DB}")))


def copy_kb(dst: Path, files: list[str] | None = None) -> Path:
    if files is None:
        shutil.copytree(KB_DIR, dst)
        return dst
    for rel in files:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(KB_DIR / rel, dst / rel)
    return dst


class RagEnv:
    def __init__(self, collection: str) -> None:
        self.collection = collection
        self.redis = redis_db15()
        self.qdrant: AsyncQdrantClient = make_client()
        self.manifest = Manifest(self.redis, key=f"kb:manifest:{collection}")

    def embedder(self) -> CachedEmbeddings:
        return embeddings(self.redis)  # instance mới → đếm hits/misses riêng mỗi lần ingest

    async def ingest(self, kb_dir: Path, *, recreate: bool = False) -> tuple[IngestReport, CachedEmbeddings]:
        emb = self.embedder()
        report = await run_ingest(
            kb_dir,
            qdrant=self.qdrant,
            manifest=self.manifest,
            embedder=emb,
            collection=self.collection,
            recreate=recreate,
        )
        return report, emb

    async def drop(self) -> None:
        await self.qdrant.delete_collection(self.collection)
        await self.manifest.clear()

    async def close(self) -> None:
        await self.qdrant.close()
        await self.redis.aclose()
