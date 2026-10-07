import json

from redis.asyncio import Redis

from shared import redis_keys as keys
from shared.ids import now_ms, uuid7


async def save_turn(redis: Redis, job: dict[str, str], final: dict, steps: list[dict] | None = None) -> str:
    """Một transaction: 2 message, danh sách conversation, trạng thái job. `final` là FinalPayload (JSON)."""
    cid, job_id = job["conversation_id"], job["job_id"]
    user_text = json.loads(job["input"])["text"]
    user_msg_id, ai_id = str(uuid7()), str(uuid7())
    ts = now_ms()
    owner = {"job_id": job_id, "user_id": job["user_id"], "conversation_id": cid, "created_at": ts}
    user_msg = {"id": user_msg_id, "role": "user", "content_md": user_text, **owner}
    ai_msg = {
        "id": ai_id,
        "role": "assistant",
        "content_md": final["answer_md"],
        **owner,
        "status": final["status"],
        "citations": final["citations"],
        "confidence": final["confidence"],
        "missing_info": final["missing_info"],
        "artifact": final["artifact"],
        "artifact_md": final["artifact_md"],
        "compliance": final["compliance"],
        "steps": steps or [],  # các bước agent (node, label, duration_ms)
    }
    async with redis.pipeline(transaction=True) as p:
        p.set(keys.msg(user_msg_id), json.dumps(user_msg, ensure_ascii=False), ex=keys.TTL_30D)
        p.set(keys.msg(ai_id), json.dumps(ai_msg, ensure_ascii=False), ex=keys.TTL_30D)
        p.rpush(keys.conv_msgs(cid), user_msg_id, ai_id)
        p.expire(keys.conv_msgs(cid), keys.TTL_30D)
        p.set(keys.job_msg(job_id), ai_id, ex=keys.TTL_7D)
        p.hset(keys.conv(cid), mapping={"updated_at": ts, "active_job_id": ""})
        p.hset(keys.job(job_id), mapping={"status": "succeeded", "finished_at": ts})
        await p.execute()
    return ai_id
