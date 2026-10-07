from fastapi import Request
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from shared.lua import Scripts


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_scripts(request: Request) -> Scripts:
    return request.app.state.scripts


def get_qdrant(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant
