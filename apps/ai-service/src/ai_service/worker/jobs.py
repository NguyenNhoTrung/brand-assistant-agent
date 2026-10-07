import json

from redis.asyncio import Redis

from shared import redis_keys as keys
from shared.ids import now_ms


async def get(redis: Redis, job_id: str) -> dict[str, str] | None:
    h = await redis.hgetall(keys.job(job_id))
    if not h:
        return None
    return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in h.items()}


async def mark_running(redis: Redis, job_id: str) -> None:
    await redis.hset(keys.job(job_id), mapping={"status": "running", "started_at": now_ms()})


async def finish(redis: Redis, job: dict[str, str], status: str, error: dict | None = None) -> None:
    """Kết thúc job không đi qua `store.save_turn` (hủy, lỗi, ingest) — nhả `active_job_id` của conversation."""
    mapping: dict = {"status": status, "finished_at": now_ms()}
    if error:
        mapping["error"] = json.dumps(error)
    await redis.hset(keys.job(job["job_id"]), mapping=mapping)
    cid = job.get("conversation_id")
    if cid and await redis.hget(keys.conv(cid), "active_job_id") in (job["job_id"], job["job_id"].encode()):
        await redis.hset(keys.conv(cid), "active_job_id", "")
