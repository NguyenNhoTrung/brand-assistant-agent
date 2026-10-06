from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from gateway.api import auth, events, health, jobs
from gateway.core.auth import UserStore
from gateway.core.errors import Problem, problem_handler, validation_handler
from gateway.settings import settings
from shared.lua import Scripts


def create_app(redis: Redis | None = None, users: UserStore | None = None) -> FastAPI:
    """App factory — test truyền fakeredis và UserStore riêng."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.redis = redis or Redis.from_url(settings.redis_url)
        app.state.scripts = Scripts(app.state.redis)
        app.state.users = users or UserStore.from_file(settings.users_file)
        yield
        if redis is None:
            await app.state.redis.aclose()

    app = FastAPI(title="Company Brain Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    app.add_exception_handler(Problem, problem_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    for r in (health.router, auth.router, jobs.router, events.router):
        app.include_router(r)
    # TODO(P0): conversations, sources, feedback · TODO(P1): admin (traces, ingest, kb)
    return app


app = create_app()
