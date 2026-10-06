from fastapi import Request
from redis.asyncio import Redis

from shared.lua import Scripts


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_scripts(request: Request) -> Scripts:
    return request.app.state.scripts
