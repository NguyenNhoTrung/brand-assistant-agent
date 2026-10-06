import asyncio
import signal

import structlog
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis

from ai_service.agent.graph import build_graph
from ai_service.settings import settings
from ai_service.worker.loop import Worker

log = structlog.get_logger()


async def main() -> None:
    settings.require_openai_key()  # fail fast, không chờ tới job đầu tiên
    redis = Redis.from_url(settings.redis_url)
    async with AsyncRedisSaver.from_conn_string(settings.redis_url) as saver:
        await saver.asetup()
        worker = Worker(redis, build_graph(saver))
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, worker.stopping.set)
        log.info("worker.started", concurrency=settings.worker_concurrency, models_file=settings.models_file)
        await worker.run()
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
