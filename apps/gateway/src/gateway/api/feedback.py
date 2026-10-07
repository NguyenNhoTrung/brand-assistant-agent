from uuid import UUID

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from gateway.core.auth import User, current_user
from gateway.core.redis import get_redis
from gateway.services import messages
from shared.contracts import Feedback, MessageView

router = APIRouter(tags=["feedback"])


@router.post("/v1/messages/{message_id}/feedback")
async def give_feedback(
    message_id: UUID, body: Feedback, user: User = Depends(current_user), redis: Redis = Depends(get_redis)
) -> MessageView:
    """👍/👎 + comment — gửi lại sẽ ghi đè lần trước."""
    return await messages.set_feedback(redis, message_id, user.id, body)
