import json
from uuid import UUID

from redis.asyncio import Redis

from gateway.core.errors import Problem
from shared import redis_keys as keys
from shared.contracts import Feedback, FinalPayload, MessageView


async def get_raw(redis: Redis, msg_id: UUID | str) -> dict | None:
    raw = await redis.get(keys.msg(msg_id))
    return json.loads(raw) if raw else None


async def list_by_ids(redis: Redis, ids: list[str]) -> list[MessageView]:
    if not ids:
        return []
    raws = await redis.mget([keys.msg(i) for i in ids])
    return [MessageView.model_validate(json.loads(r)) for r in raws if r]  # message hết hạn → bỏ qua


async def final_of_job(redis: Redis, job_id: UUID | str) -> FinalPayload | None:
    """`job:{id}:msg` → `msg:{id}` → FinalPayload (khi stream event đã hết hạn / polling)."""
    msg_id = await redis.get(keys.job_msg(job_id))
    msg = await get_raw(redis, msg_id.decode() if isinstance(msg_id, bytes) else msg_id) if msg_id else None
    if msg is None:
        return None
    return FinalPayload.model_validate({**msg, "answer_md": msg["content_md"]})


async def set_feedback(redis: Redis, msg_id: UUID, user_id: str, feedback: Feedback) -> MessageView:
    msg = await get_raw(redis, msg_id)
    if msg is None or msg.get("user_id") != user_id:
        raise Problem(404, "message_not_found")  # 404 thay vì 403 → không lộ sự tồn tại
    if msg["role"] != "assistant":
        raise Problem(422, "validation_error", "Chỉ đánh giá được câu trả lời của assistant")
    msg["feedback"] = feedback.model_dump()
    await redis.set(keys.msg(msg_id), json.dumps(msg, ensure_ascii=False), keepttl=True)
    return MessageView.model_validate(msg)
