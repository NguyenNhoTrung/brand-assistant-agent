import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from redis.asyncio import Redis

from gateway.core.auth import User, require_admin
from gateway.core.errors import Problem
from gateway.core.redis import get_redis, get_scripts
from gateway.services import jobs
from gateway.services.redis_util import s
from shared import redis_keys as keys
from shared.contracts import IngestRequest, JobCreated, KbEntry
from shared.ids import now_ms, uuid7
from shared.lua import Scripts

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/ingest", status_code=202)
async def ingest(
    response: Response,
    body: IngestRequest | None = None,
    idem_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
    scripts: Scripts = Depends(get_scripts),
) -> JobCreated:
    """Đẩy job `ingest` (worker nạp lại `data/knowledge`). Theo dõi bằng `/v1/jobs/{id}/events`."""
    recreate = body.recreate if body else False
    created, jid = await scripts.create_job(
        job_id=str(uuid7()),
        user_id=user.id,
        conversation_id="",  # job ingest không thuộc conversation nào
        idem_key=idem_key or uuid7().hex,
        input_json=json.dumps({"text": "ingest", "mode": "auto", "recreate": recreate}),
        now_ms=now_ms(),
        job_type="ingest",
        title="ingest",
    )
    job = await jobs.get(redis, jid)
    if job is None:
        raise Problem(404, "job_not_found")
    if not created:
        response.status_code = 200
    return JobCreated(job_id=job.job_id, conversation_id=None, status=job.status, events_url=f"/v1/jobs/{jid}/events")


@router.get("/kb")
async def knowledge_base(redis: Redis = Depends(get_redis)) -> list[KbEntry]:
    """`kb:manifest` — tài liệu đã ingest, trạng thái active/superseded."""
    raw = await redis.hgetall(keys.KB_MANIFEST)
    entries = [KbEntry(source_path=s(k), **json.loads(v)) for k, v in raw.items()]
    return sorted(entries, key=lambda e: e.source_path)


@router.get("/traces")
async def traces(limit: int = Query(default=50, ge=1, le=200), redis: Redis = Depends(get_redis)) -> list[dict]:
    """Trace mới nhất (`traces:recent`) — tóm tắt; chi tiết ở `/admin/jobs/{id}/trace`."""
    rows: Any = await redis.zrevrange(keys.TRACES_RECENT, 0, limit - 1, withscores=True)
    if not rows:
        return []
    raws = await redis.mget([keys.trace(s(jid)) for jid, _ in rows])
    out = []
    for (jid, score), raw in zip(rows, raws, strict=True):
        if raw is None:  # trace hết hạn
            continue
        t = json.loads(raw)
        out.append(
            {
                "job_id": s(jid),
                "recorded_at": int(score),
                "user_id": t.get("user_id"),
                "input": t.get("input"),
                "scores": t.get("scores"),
                "usage": t.get("usage"),
            }
        )
    return out


@router.get("/jobs/{job_id}/trace")
async def job_trace(job_id: UUID, redis: Redis = Depends(get_redis)) -> dict:
    raw = await redis.get(keys.trace(job_id))
    if raw is None:
        raise Problem(404, "job_not_found", "Không có trace cho job này")
    return json.loads(raw)
