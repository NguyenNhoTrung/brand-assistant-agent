from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from redis.asyncio import Redis

from gateway.core.auth import User, current_user
from gateway.core.errors import Problem
from gateway.core.redis import get_redis, get_scripts
from gateway.services import jobs
from shared import redis_keys as keys
from shared.contracts import JobCreate, JobCreated, JobView
from shared.ids import now_ms, uuid7
from shared.lua import Scripts

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.post("", status_code=202)
async def create_job(
    body: JobCreate,
    response: Response,
    idem_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(current_user),
    redis: Redis = Depends(get_redis),
    scripts: Scripts = Depends(get_scripts),
) -> JobCreated:
    cid = body.conversation_id or uuid7()
    if body.conversation_id and await jobs.conversation_owner(redis, cid) != user.id:
        raise Problem(404, "conversation_not_found")
    created, jid = await scripts.create_job(
        job_id=str(uuid7()),
        user_id=user.id,
        conversation_id=str(cid),
        idem_key=idem_key,
        input_json=body.input.model_dump_json(),
        now_ms=now_ms(),
        job_type="chat",
        title=body.input.text[:60],
    )
    if not created:  # trùng Idempotency-Key → trả job cũ
        response.status_code = 200
        job = await jobs.get(redis, jid)
        if job is None:
            raise Problem(404, "job_not_found")
        return JobCreated(
            job_id=job.job_id,
            conversation_id=job.conversation_id,
            status=job.status,
            events_url=f"/v1/jobs/{jid}/events",
        )
    return JobCreated(job_id=UUID(jid), conversation_id=cid, status="queued", events_url=f"/v1/jobs/{jid}/events")


@router.get("/{job_id}")
async def get_job(job_id: UUID, user: User = Depends(current_user), redis: Redis = Depends(get_redis)) -> JobView:
    """Trạng thái job; job chat `succeeded` kèm `result` (fallback polling khi không dùng SSE)."""
    return await jobs.with_result(redis, await jobs.get_owned(redis, job_id, user.id))


@router.post("/{job_id}/cancel", status_code=202)
async def cancel_job(job_id: UUID, user: User = Depends(current_user), redis: Redis = Depends(get_redis)) -> dict:
    job = await jobs.get_owned(redis, job_id, user.id)
    if not job.is_terminal:  # job đã kết thúc → hủy là no-op
        await redis.set(keys.job_cancel(job_id), 1, ex=keys.TTL_1H)
    return {"ok": True}
