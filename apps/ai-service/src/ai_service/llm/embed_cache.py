"""Cache embedding trong Redis: `emb:{model}:{sha256(text)}` → vector float32 (§13.3).

Ingest lại / Qdrant mất dữ liệu → dựng lại index mà không gọi OpenAI lần nữa.
"""

import hashlib
from typing import TYPE_CHECKING

import numpy as np
from langchain_core.embeddings import Embeddings

from shared import redis_keys as keys
from shared.redis_keys import TTL_7D

if TYPE_CHECKING:  # chỉ cần cho type — agent không được kéo redis vào lúc chạy (.importlinter)
    from redis.asyncio import Redis


class CachedEmbeddings(Embeddings):
    def __init__(self, inner: Embeddings, redis: "Redis", model: str, ttl: int = TTL_7D) -> None:
        self.inner, self.redis, self.model, self.ttl = inner, redis, model, ttl
        self.hits = 0
        self.misses = 0  # số text phải gọi model thật — test dùng để kiểm tra cache

    def _key(self, text: str) -> str:
        return keys.emb(self.model, hashlib.sha256(text.encode()).hexdigest())

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cached: list[bytes | str | None] = list(await self.redis.mget([self._key(t) for t in texts]))
        missing = [i for i, v in enumerate(cached) if v is None]
        self.hits += len(texts) - len(missing)
        self.misses += len(missing)
        if missing:
            fresh = await self.inner.aembed_documents([texts[i] for i in missing])
            async with self.redis.pipeline(transaction=False) as p:
                for i, vec in zip(missing, fresh, strict=True):
                    blob = np.asarray(vec, dtype=np.float32).tobytes()
                    cached[i] = blob
                    p.set(self._key(texts[i]), blob, ex=self.ttl)
                await p.execute()
        out = []
        for v in cached:
            if not isinstance(v, bytes):  # vector là bytes thô
                raise TypeError("CachedEmbeddings cần client Redis với decode_responses=False")
            out.append(np.frombuffer(v, dtype=np.float32).tolist())
        return out

    async def aembed_query(self, text: str) -> list[float]:
        return (await self.aembed_documents([text]))[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("CachedEmbeddings chỉ hỗ trợ async")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("CachedEmbeddings chỉ hỗ trợ async")
