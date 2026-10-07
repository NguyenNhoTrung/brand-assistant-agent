import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from gateway.api import admin, auth, conversations, events, feedback, health, jobs, sources
from gateway.core.auth import UserStore
from gateway.core.errors import Problem, problem_handler, unhandled_handler, validation_handler
from gateway.core.logging import configure_logging
from gateway.core.middleware import RequestContextMiddleware
from gateway.settings import settings
from shared.lua import Scripts


def _qdrant() -> AsyncQdrantClient:
    with warnings.catch_warnings():  # local/compose: api-key qua http nội bộ là cố ý
        warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
        return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=5)


def create_app(
    redis: Redis | None = None, users: UserStore | None = None, qdrant: AsyncQdrantClient | None = None
) -> FastAPI:
    """App factory — test truyền fakeredis, UserStore và Qdrant giả."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # redis-py 8 mặc định socket_timeout=5s — phải dài hơn XREAD block của SSE, nếu không client tự ném TimeoutError
        app.state.redis = redis or Redis.from_url(settings.redis_url, socket_timeout=settings.sse_block_ms / 1000 + 10)
        app.state.qdrant = qdrant or _qdrant()
        app.state.scripts = Scripts(app.state.redis)
        app.state.users = users or UserStore.from_file(settings.users_file)
        yield
        if qdrant is None:
            await app.state.qdrant.close()
        if redis is None:
            await app.state.redis.aclose()

    configure_logging()
    app = FastAPI(title="Company Brain Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        allow_credentials=False,
    )
    app.add_middleware(RequestContextMiddleware)  # thêm sau cùng = ngoài cùng → bao cả CORS
    app.add_exception_handler(Problem, problem_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(Exception, unhandled_handler)
    for r in (
        health.router,
        auth.router,
        jobs.router,
        events.router,
        conversations.router,
        feedback.router,
        sources.router,
        admin.router,
    ):
        app.include_router(r)
    return app


app = create_app()
