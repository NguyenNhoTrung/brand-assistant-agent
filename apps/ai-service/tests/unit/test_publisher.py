import json

import fakeredis

from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys


async def test_tokens_are_batched_and_flushed_before_other_events():
    r = fakeredis.FakeAsyncRedis()
    pub = EventPublisher(r, "j1")
    pub.FLUSH_S = 999
    for t in ["Xin ", "chào", "!"]:
        await pub.token(t)
    await pub.emit("message.completed", {})
    await pub.close()
    entries = await r.xrange(keys.job_events("j1"))
    types = [e[1][b"type"].decode() for e in entries]
    assert types == ["token", "message.completed"]
    assert json.loads(entries[0][1][b"data"])["data"]["delta"] == "Xin chào!"
    assert await r.ttl(keys.job_events("j1")) > 0
