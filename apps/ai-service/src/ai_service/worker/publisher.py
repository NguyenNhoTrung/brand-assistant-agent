import json
import time
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from shared import redis_keys as keys


class EventPublisher:
    """Ghi event vào `job:{id}:events`. Gộp token: flush mỗi ~50 ms hoặc > 64 ký tự."""

    FLUSH_S = 0.05
    FLUSH_CHARS = 64

    def __init__(self, redis: Redis, job_id: str):
        self.redis, self.job_id, self.key = redis, job_id, keys.job_events(job_id)
        self._buf: list[str] = []
        self._last = time.monotonic()

    async def emit(self, type_: str, data: Any) -> None:
        await self._flush_tokens()
        await self._xadd(type_, data)

    async def token(self, delta: str) -> None:
        self._buf.append(delta)
        if sum(map(len, self._buf)) > self.FLUSH_CHARS or time.monotonic() - self._last > self.FLUSH_S:
            await self._flush_tokens()

    async def close(self) -> None:
        await self._flush_tokens()
        await self.redis.expire(self.key, keys.TTL_1H)

    async def _flush_tokens(self) -> None:
        if self._buf:
            delta, self._buf = "".join(self._buf), []
            await self._xadd("token", {"delta": delta})
        self._last = time.monotonic()

    async def _xadd(self, type_: str, data: Any) -> None:
        envelope = {"v": 1, "job_id": self.job_id, "ts": datetime.now(UTC).isoformat(), "data": data}
        await self.redis.xadd(
            self.key,
            {"type": type_, "data": json.dumps(envelope, ensure_ascii=False)},
            maxlen=keys.EVENTS_MAXLEN,
            approximate=True,
        )
