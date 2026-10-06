import asyncio

import structlog
from redis.asyncio import Redis

from ai_service.agent.graph import Graph
from ai_service.settings import settings
from ai_service.worker import jobs
from ai_service.worker.handlers import HANDLERS, JobCancelled
from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys

log = structlog.get_logger()


def _error(e: BaseException) -> dict:
    if isinstance(e, TimeoutError):
        return {"code": "job_timeout", "message": "Job vượt quá thời gian cho phép"}
    return {"code": "internal_error", "message": type(e).__name__}


class Worker:
    def __init__(self, redis: Redis, graph: Graph):
        self.redis, self.graph = redis, graph
        self.stopping = asyncio.Event()

    async def run(self) -> None:
        tasks = [asyncio.create_task(self.loop()) for _ in range(settings.worker_concurrency)]
        await self.stopping.wait()  # SIGTERM
        await asyncio.wait(tasks, timeout=30)  # chờ job đang chạy tối đa 30s

    async def loop(self) -> None:
        while not self.stopping.is_set():
            item = await self.redis.brpop([keys.QUEUE], timeout=5)
            if item is not None:
                await self.process(item[1].decode() if isinstance(item[1], bytes) else item[1])

    async def process(self, job_id: str) -> None:
        job = await jobs.get(self.redis, job_id)
        if job is None or job.get("status") != "queued":
            return
        job["job_id"] = job_id
        pub = EventPublisher(self.redis, job_id)
        log.info("job.started", job_id=job_id, type=job["type"])
        try:
            if await self.redis.exists(keys.job_cancel(job_id)):
                raise JobCancelled()
            await jobs.mark_running(self.redis, job_id)
            await asyncio.wait_for(
                HANDLERS[job["type"]](self.redis, self.graph, job, pub), timeout=settings.job_timeout_s
            )
        except JobCancelled:
            await jobs.finish(self.redis, job_id, "cancelled")
            await pub.emit("job.cancelled", {})
        except Exception as e:
            log.exception("job.failed", job_id=job_id)
            await jobs.finish(self.redis, job_id, "failed", error=_error(e))
            await pub.emit("job.failed", _error(e))
        finally:
            await pub.close()
