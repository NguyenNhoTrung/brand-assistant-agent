import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from gateway.core.auth import User, current_user
from gateway.core.redis import get_redis
from gateway.services import jobs
from gateway.settings import settings
from shared import redis_keys as keys
from shared.contracts import TERMINAL_EVENTS

router = APIRouter(tags=["events"])


def _s(v: bytes | str) -> str:
    return v.decode() if isinstance(v, bytes) else v


@router.get("/v1/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    redis: Redis = Depends(get_redis),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    job = await jobs.get_owned(redis, job_id, user.id)
    key = keys.job_events(job_id)

    async def stream() -> AsyncIterator[dict]:
        if job.is_terminal and not await redis.exists(key):
            # TODO(P0): stream đã hết hạn → dựng message.completed từ msg:{id}
            yield {"event": "job." + job.status, "data": json.dumps({"status": job.status})}
            return
        cursor = last_event_id or "0-0"
        while not await request.is_disconnected():
            resp: Any = await redis.xread({key: cursor}, block=settings.sse_block_ms, count=100)
            if not resp:
                current = await jobs.get(redis, job_id)
                if current and (await jobs.expire_if_stale(redis, current)).status == "failed":
                    yield {"event": "job.failed", "data": json.dumps({"code": "job_timeout"})}
                    return
                yield {"event": "heartbeat", "data": "{}"}
                continue
            for entry_id, fields in resp[0][1]:
                cursor = _s(entry_id)
                f = {_s(k): _s(v) for k, v in fields.items()}
                yield {"id": cursor, "event": f["type"], "data": f["data"]}
                if f["type"] in TERMINAL_EVENTS:
                    return

    return EventSourceResponse(stream(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
