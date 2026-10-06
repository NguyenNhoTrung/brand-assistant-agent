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


async def finish(redis: Redis, job_id: str, status: str, error: dict | None = None) -> None:
    mapping: dict = {"status": status, "finished_at": now_ms()}
    if error:
        mapping["error"] = json.dumps(error)
    await redis.hset(keys.job(job_id), mapping=mapping)
