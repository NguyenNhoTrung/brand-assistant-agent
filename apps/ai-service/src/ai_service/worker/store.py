import json

from redis.asyncio import Redis

from shared import redis_keys as keys
from shared.ids import now_ms, uuid7


async def save_turn(redis: Redis, job: dict[str, str], final: dict) -> str:
    """Một transaction: 2 message, danh sách conversation, trạng thái job."""
    cid, job_id = job["conversation_id"], job["job_id"]
    user_text = json.loads(job["input"])["text"]
    user_id, ai_id = str(uuid7()), str(uuid7())
    user_msg = {"id": user_id, "role": "user", "content_md": user_text, "job_id": job_id}
    ai_msg = {"id": ai_id, "role": "assistant", "content_md": final["answer_md"], "job_id": job_id, **final}
    async with redis.pipeline(transaction=True) as p:
        p.set(keys.msg(user_id), json.dumps(user_msg, ensure_ascii=False), ex=keys.TTL_30D)
        p.set(keys.msg(ai_id), json.dumps(ai_msg, ensure_ascii=False), ex=keys.TTL_30D)
        p.rpush(keys.conv_msgs(cid), user_id, ai_id)
        p.set(keys.job_msg(job_id), ai_id, ex=keys.TTL_7D)
        p.hset(keys.conv(cid), mapping={"updated_at": now_ms(), "active_job_id": ""})
        p.hset(keys.job(job_id), mapping={"status": "succeeded", "finished_at": now_ms()})
        await p.execute()
    return ai_id
