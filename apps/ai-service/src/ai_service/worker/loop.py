import asyncio
import time

import openai
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from structlog.contextvars import bound_contextvars

from ai_service.settings import settings
from ai_service.worker import jobs
from ai_service.worker.handlers import HANDLERS, Deps, JobCancelled, JobError
from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys

log = structlog.get_logger()

# redis-py 8 mặc định socket_timeout=5s → BRPOP phải block NGẮN hơn, nếu không client tự ném TimeoutError
BRPOP_TIMEOUT_S = 2
SHUTDOWN_ERROR = {"code": "job_timeout", "message": "Worker dừng khi job đang chạy"}


def _error(e: BaseException) -> dict:
    if isinstance(e, JobError):
        return {"code": e.code, "message": str(e)}
    if isinstance(e, TimeoutError):  # asyncio.wait_for hết JOB_TIMEOUT_S
        return {"code": "job_timeout", "message": "Job vượt quá thời gian cho phép"}
    if isinstance(e, openai.APIConnectionError | openai.RateLimitError | openai.InternalServerError):
        return {"code": "llm_unavailable", "message": "OpenAI tạm thời không phản hồi — thử lại sau"}
    return {"code": "internal_error", "message": type(e).__name__}


class Worker:
    def __init__(self, deps: Deps):
        self.deps = deps
        self.redis: Redis = deps.redis
        self.stopping = asyncio.Event()

    async def run(self) -> None:
        tasks = [asyncio.create_task(self.loop()) for _ in range(settings.worker_concurrency)]
        await self.stopping.wait()  # SIGTERM / Ctrl+C
        log.info("worker.stopping", grace_s=settings.shutdown_grace_s)
        _, pending = await asyncio.wait(tasks, timeout=settings.shutdown_grace_s)
        for t in pending:  # job chạy quá thời gian ân hạn → cắt, process() ghi job.failed
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        log.info("worker.stopped", interrupted=len(pending))

    async def loop(self) -> None:
        while not self.stopping.is_set():
            try:
                item = await self.redis.brpop([keys.QUEUE], timeout=BRPOP_TIMEOUT_S)
            except RedisError:  # Redis restart / mất kết nối → thử lại, không để task chết im lặng
                log.exception("worker.brpop_failed")
                await asyncio.sleep(1)
                continue
            if item is not None:
                await self.process(item[1].decode() if isinstance(item[1], bytes) else item[1])

    async def process(self, job_id: str) -> None:
        job = await jobs.get(self.redis, job_id)
        if job is None or job.get("status") != "queued":
            log.warning("job.skipped", job_id=job_id, status=job and job.get("status"))
            return
        job["job_id"] = job_id
        pub = EventPublisher(self.redis, job_id)
        with bound_contextvars(job_id=job_id, job_type=job.get("type")):
            t0 = time.monotonic()
            log.info("job.started")
            try:
                if await self.redis.exists(keys.job_cancel(job_id)):
                    raise JobCancelled()
                await jobs.mark_running(self.redis, job_id)
                await asyncio.wait_for(HANDLERS[job["type"]](self.deps, job, pub), timeout=settings.job_timeout_s)
                log.info("job.succeeded", duration_ms=round((time.monotonic() - t0) * 1000))
            except JobCancelled:
                await jobs.finish(self.redis, job, "cancelled")
                await pub.emit("job.cancelled", {})
                log.info("job.cancelled")
            except asyncio.CancelledError:
                await jobs.finish(self.redis, job, "failed", error=SHUTDOWN_ERROR)
                await pub.emit("job.failed", SHUTDOWN_ERROR)
                log.warning("job.interrupted")
                raise
            except Exception as e:
                log.exception("job.failed", code=_error(e)["code"])
                await jobs.finish(self.redis, job, "failed", error=_error(e))
                await pub.emit("job.failed", _error(e))
            finally:
                await pub.close()
