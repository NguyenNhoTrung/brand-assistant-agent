from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from gateway.core.errors import Problem
from gateway.services import messages
from gateway.services.redis_util import decode_hash, s
from shared import redis_keys as keys
from shared.contracts import ConversationView, MessageView


async def list_for_user(redis: Redis, user_id: str, limit: int) -> list[ConversationView]:
    raw: Any = await redis.zrevrange(keys.user_convs(user_id), 0, limit - 1)
    ids = [s(i) for i in raw]
    async with redis.pipeline(transaction=False) as p:
        for cid in ids:
            p.hgetall(keys.conv(cid))
        hashes = await p.execute()
    out = []
    for cid, h in zip(ids, hashes, strict=True):
        if not h:  # conversation hết hạn nhưng còn trong sorted set
            continue
        c = decode_hash(h)
        out.append(
            ConversationView(
                id=UUID(cid),
                title=c.get("title", ""),
                updated_at=int(c.get("updated_at", 0)),
                active_job_id=UUID(c["active_job_id"]) if c.get("active_job_id") else None,
            )
        )
    return out


async def get_owned(redis: Redis, conv_id: UUID, user_id: str) -> dict[str, str]:
    c = decode_hash(await redis.hgetall(keys.conv(conv_id)))
    if not c or c.get("user_id") != user_id:
        raise Problem(404, "conversation_not_found")
    return c


async def messages_of(redis: Redis, conv_id: UUID) -> list[MessageView]:
    ids = [s(i) for i in await redis.lrange(keys.conv_msgs(conv_id), 0, -1)]
    return await messages.list_by_ids(redis, ids)
