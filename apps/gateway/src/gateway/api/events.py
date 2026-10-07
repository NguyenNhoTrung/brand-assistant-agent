import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from gateway.core.auth import User, current_user
from gateway.core.errors import Problem
from gateway.core.redis import get_redis
from gateway.services import jobs, messages
from gateway.services.redis_util import s
from gateway.settings import settings
from shared import redis_keys as keys
from shared.contracts import TERMINAL_EVENTS, EventEnvelope, FinalPayload, JobView

router = APIRouter(tags=["events"])

_STREAM_ID = re.compile(r"^\d+-\d+$")


def _sse(job_id: UUID, type_: str, data: dict[str, Any]) -> dict[str, str]:
    """Event gateway tự dựng — cùng envelope với event worker ghi vào stream (§7.2)."""
    env = EventEnvelope(job_id=str(job_id), ts=datetime.now(UTC).isoformat(), data=data)
    return {"event": type_, "data": env.model_dump_json()}


async def terminal_event(redis: Redis, job: JobView) -> dict[str, str]:
    """Stream đã hết hạn (EXPIRE 1h) hoặc worker chết → dựng event kết thúc từ `job:{id}` + `msg:{id}`."""
    if job.status == "failed":
        return _sse(job.job_id, "job.failed", job.error or {"code": "internal_error", "message": "unknown"})
    if job.status == "cancelled":
        return _sse(job.job_id, "job.cancelled", {})
    final = await messages.final_of_job(redis, job.job_id) or FinalPayload(
        status="answered", answer_md="Job đã hoàn tất — kết quả không còn lưu trữ."
    )
    return _sse(job.job_id, "message.completed", final.model_dump(mode="json"))


@router.get("/v1/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    user: User = Depends(current_user),
    redis: Redis = Depends(get_redis),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """SSE: replay từ đầu (hoặc sau `Last-Event-ID`) rồi theo dõi tới event kết thúc; heartbeat mỗi 15 s."""
    if last_event_id and not _STREAM_ID.match(last_event_id):
        raise Problem(422, "validation_error", "Last-Event-ID không hợp lệ")
    job = await jobs.get_owned(redis, job_id, user.id)
    key = keys.job_events(job_id)

    async def stream() -> AsyncIterator[dict]:
        if job.is_terminal and not await redis.exists(key):
            yield await terminal_event(redis, job)
            return
        cursor = last_event_id or "0-0"
        while not await request.is_disconnected():
            resp: Any = await redis.xread({key: cursor}, block=settings.sse_block_ms, count=100)
            if not resp:
                current = await jobs.get(redis, job_id)
                if current is None:
                    return
                current = await jobs.expire_if_stale(redis, current)
                if current.is_terminal:  # worker chết (job_timeout) / resume sau event kết thúc → đóng stream
                    yield await terminal_event(redis, current)
                    return
                yield {"event": "heartbeat", "data": "{}"}
                continue
            for entry_id, fields in resp[0][1]:
                cursor = s(entry_id)
                f = {s(k): s(v) for k, v in fields.items()}
                yield {"id": cursor, "event": f["type"], "data": f["data"]}
                if f["type"] in TERMINAL_EVENTS:
                    return

    return EventSourceResponse(stream(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
