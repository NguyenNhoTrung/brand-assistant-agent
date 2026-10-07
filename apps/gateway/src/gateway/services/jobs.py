import json
from uuid import UUID

import structlog
from redis.asyncio import Redis

from gateway.core.errors import Problem
from gateway.services import messages
from gateway.services.redis_util import decode_hash, s
from gateway.settings import settings
from shared import redis_keys as keys
from shared.contracts import JobView
from shared.ids import now_ms

STALE_ERROR = {"code": "job_timeout", "message": "Worker không phản hồi"}


async def get(redis: Redis, job_id: UUID | str) -> JobView | None:
    h = decode_hash(await redis.hgetall(keys.job(job_id)))
    if not h:
        return None
    return JobView.model_validate(
        {
            **h,
            "job_id": job_id,
            "conversation_id": h.get("conversation_id") or None,
            "input": json.loads(h["input"]),
            "error": json.loads(h["error"]) if h.get("error") else None,
            "started_at": h.get("started_at") or None,
            "finished_at": h.get("finished_at") or None,
        }
    )


async def get_owned(redis: Redis, job_id: UUID, user_id: str) -> JobView:
    job = await get(redis, job_id)
    if job is None or job.user_id != user_id:
        raise Problem(404, "job_not_found")  # 404 thay vì 403 → không lộ sự tồn tại
    structlog.contextvars.bind_contextvars(job_id=str(job_id))
    return await expire_if_stale(redis, job)


async def with_result(redis: Redis, job: JobView) -> JobView:
    if job.status != "succeeded" or job.type != "chat":
        return job
    return job.model_copy(update={"result": await messages.final_of_job(redis, job.job_id)})


def is_stale(job: JobView) -> bool:
    limit_ms = (settings.job_timeout_s + 30) * 1000
    return job.status == "running" and job.started_at is not None and now_ms() - job.started_at > limit_ms


async def expire_if_stale(redis: Redis, job: JobView) -> JobView:
    """Worker chết giữa chừng → phát hiện lazy, chuyển job sang failed/job_timeout (§4.2)."""
    if not is_stale(job):
        return job
    mapping = {"status": "failed", "finished_at": now_ms(), "error": json.dumps(STALE_ERROR)}
    await redis.hset(keys.job(job.job_id), mapping=mapping)  # type: ignore[arg-type]
    if job.conversation_id and s(await redis.hget(keys.conv(job.conversation_id), "active_job_id") or "") == str(
        job.job_id
    ):
        await redis.hset(keys.conv(job.conversation_id), "active_job_id", "")
    return job.model_copy(update={"status": "failed", "error": STALE_ERROR})


async def conversation_owner(redis: Redis, conversation_id: UUID) -> str | None:
    owner = await redis.hget(keys.conv(conversation_id), "user_id")
    return s(owner) if owner else None
