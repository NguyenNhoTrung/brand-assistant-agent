"""`kb:manifest` — sổ ghi ingest: path → {content_hash, chunk_count, status, ...} (§5, §10.2)."""

import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

from shared.redis_keys import KB_MANIFEST


@dataclass(frozen=True)
class ManifestEntry:
    content_hash: str
    chunk_count: int
    status: str  # active | superseded
    title: str
    doc_type: str
    version: int
    effective_date: str
    ingested_at: str


class Manifest:
    def __init__(self, redis: Redis, key: str = KB_MANIFEST) -> None:
        self.redis, self.key = redis, key

    async def all(self) -> dict[str, ManifestEntry]:
        raw = await self.redis.hgetall(self.key)
        return {_s(k): ManifestEntry(**json.loads(v)) for k, v in raw.items()}

    async def put(self, source_path: str, entry: ManifestEntry) -> None:
        await self.redis.hset(self.key, source_path, json.dumps(asdict(entry)))

    async def remove(self, source_path: str) -> None:
        await self.redis.hdel(self.key, source_path)

    async def clear(self) -> None:
        await self.redis.delete(self.key)


def _s(v: bytes | str) -> str:
    return v.decode() if isinstance(v, bytes) else v
