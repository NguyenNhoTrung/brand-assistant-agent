from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from gateway.core.errors import Problem
from gateway.core.redis import get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@router.get("/readyz")
async def readyz(redis: Redis = Depends(get_redis)) -> dict:
    try:
        await redis.ping()
    except Exception as e:
        raise Problem(500, "internal_error", f"redis: {e}") from e
    # TODO(P0): kiểm tra Qdrant khi gateway bắt đầu đọc /v1/sources
    return {"ok": True}
