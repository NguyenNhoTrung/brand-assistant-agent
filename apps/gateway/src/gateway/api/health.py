import asyncio

from fastapi import APIRouter, Depends
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from gateway.core.errors import Problem
from gateway.core.redis import get_qdrant, get_redis

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@router.get("/readyz")
async def readyz(redis: Redis = Depends(get_redis), qdrant: AsyncQdrantClient = Depends(get_qdrant)) -> dict:
    """Redis + Qdrant đều trả lời (Qdrant cần cho hover citation `/v1/sources`)."""
    try:
        await asyncio.wait_for(redis.ping(), 2)
    except Exception as e:
        raise Problem(503, "internal_error", f"redis: {type(e).__name__}") from e
    try:
        await asyncio.wait_for(qdrant.get_collections(), 2)
    except Exception as e:
        raise Problem(503, "internal_error", f"qdrant: {type(e).__name__}") from e
    return {"ok": True}
