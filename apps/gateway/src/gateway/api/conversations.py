from uuid import UUID

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from gateway.core.auth import User, current_user
from gateway.core.redis import get_redis
from gateway.services import conversations, jobs
from gateway.settings import settings
from shared.contracts import ConversationView, JobView, MessageView

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    user: User = Depends(current_user), redis: Redis = Depends(get_redis)
) -> list[ConversationView]:
    """Mới cập nhật trước (sidebar)."""
    return await conversations.list_for_user(redis, user.id, settings.conversations_limit)


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: UUID, user: User = Depends(current_user), redis: Redis = Depends(get_redis)
) -> list[MessageView]:
    await conversations.get_owned(redis, conversation_id, user.id)
    return await conversations.messages_of(redis, conversation_id)


@router.get("/{conversation_id}/active-job")
async def active_job(
    conversation_id: UUID, user: User = Depends(current_user), redis: Redis = Depends(get_redis)
) -> JobView | None:
    """Job đang chạy của conversation (reconnect SSE sau F5); `null` nếu không có."""
    conv = await conversations.get_owned(redis, conversation_id, user.id)
    if not conv.get("active_job_id"):
        return None
    job = await jobs.get(redis, conv["active_job_id"])
    if job is None:
        return None
    job = await jobs.expire_if_stale(redis, job)
    return None if job.is_terminal else job
