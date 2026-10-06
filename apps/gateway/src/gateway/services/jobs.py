import json
from uuid import UUID

from redis.asyncio import Redis

from gateway.core.errors import Problem
from gateway.settings import settings
from shared import redis_keys as keys
from shared.contracts import JobView
from shared.ids import now_ms


def _decode(h: dict) -> dict[str, str]:
    return {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v) for k, v in h.items()
    }


async def get(redis: Redis, job_id: UUID | str) -> JobView | None:
    h = _decode(await redis.hgetall(keys.job(job_id)))
    if not h:
        return None
    return JobView.model_validate(
        {
            **h,
            "job_id": job_id,
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
    return await expire_if_stale(redis, job)


async def expire_if_stale(redis: Redis, job: JobView) -> JobView:
    """Worker chết giữa chừng → phát hiện lazy, chuyển job sang failed/job_timeout."""
    limit_ms = (settings.job_timeout_s + 30) * 1000
    if job.status == "running" and job.started_at and now_ms() - job.started_at > limit_ms:
        error = {"code": "job_timeout", "message": "Worker không phản hồi"}
        await redis.hset(
            keys.job(job.job_id),
            mapping={"status": "failed", "finished_at": now_ms(), "error": json.dumps(error)},
        )
        return job.model_copy(update={"status": "failed", "error": error})
    return job


async def conversation_owner(redis: Redis, conversation_id: UUID) -> str | None:
    owner = await redis.hget(keys.conv(conversation_id), "user_id")
    return owner.decode() if isinstance(owner, bytes) else owner
