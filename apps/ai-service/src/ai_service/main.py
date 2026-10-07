"""`python -m ai_service.main` — worker: BRPOP `queue:jobs` → chạy graph → event vào `job:{id}:events` (§8)."""

import asyncio
import logging
import os
import signal
import sys

import structlog
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from ai_service.agent.graph import build_graph
from ai_service.compliance.rules import load_rules
from ai_service.llm.client import embeddings
from ai_service.llm.config import load_models
from ai_service.rag import sparse
from ai_service.rag.qdrant_store import make_client
from ai_service.rag.retriever import Retriever
from ai_service.settings import settings
from ai_service.skills.registry import registry
from ai_service.worker.handlers import Deps
from ai_service.worker.loop import Worker

log = structlog.get_logger()


def configure_logging() -> None:
    """Terminal → dễ đọc; container (không TTY) → JSON một dòng, có `job_id` từ contextvars."""
    tail: list[structlog.typing.Processor] = (
        [structlog.dev.ConsoleRenderer()]
        if sys.stderr.isatty()
        else [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer(ensure_ascii=False)]
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            *tail,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level.upper())),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
    structlog.contextvars.bind_contextvars(service="ai-worker", git_sha=settings.git_sha)


async def warm_up(qdrant: AsyncQdrantClient) -> None:
    """Nạp config/rules/skill + model BM25 trước job đầu tiên — lỗi cấu hình lộ ra ngay lúc khởi động."""
    load_models(settings.models_file)
    rules = load_rules()
    skills = registry()
    await asyncio.to_thread(sparse.embed_query, "warm-up")
    if not await qdrant.collection_exists(settings.qdrant_collection):
        log.warning("worker.collection_missing", collection=settings.qdrant_collection, hint="chạy ingest trước")
    log.info("worker.warmed_up", rules=len(rules), skills=sorted(skills))


async def main() -> None:
    configure_logging()
    settings.require_openai_key()  # fail fast, không chờ tới job đầu tiên
    redis = Redis.from_url(settings.redis_url)
    qdrant = make_client()
    embedder = embeddings(redis)
    try:
        await warm_up(qdrant)
        ttl = {"default_ttl": settings.checkpoint_ttl_min, "refresh_on_read": True}
        async with AsyncRedisSaver.from_conn_string(settings.redis_url, ttl=ttl) as saver:
            await saver.asetup()
            graph = build_graph(saver, retriever=Retriever(qdrant, embedder, settings.qdrant_collection))
            worker = Worker(Deps(redis, graph, qdrant, embedder))
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, worker.stopping.set)
            log.info("worker.started", concurrency=settings.worker_concurrency, models_file=settings.models_file)
            await worker.run()
    finally:
        await qdrant.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
    # onnxruntime (FastEmbed BM25) đôi khi abort lúc huỷ thread pool khi interpreter tắt trên macOS → thoát thẳng
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
