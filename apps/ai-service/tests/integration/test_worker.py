import json

import fakeredis
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ai_service.agent.graph import build_graph
from ai_service.worker.loop import Worker
from shared import redis_keys as keys
from shared.lua import Scripts


async def _enqueue(r, job_id="j1"):
    await Scripts(r).create_job(
        job_id=job_id,
        user_id="u1",
        conversation_id="c1",
        idem_key=f"k-{job_id}",
        input_json=json.dumps({"text": "Giá serum?", "mode": "qa"}),
        now_ms=1,
        job_type="chat",
        title="t",
    )


async def _types(r, job_id):
    return [e[1][b"type"].decode() for e in await r.xrange(keys.job_events(job_id))]


@pytest.mark.llm
async def test_job_runs_to_succeeded():
    r = fakeredis.FakeAsyncRedis()
    await _enqueue(r)
    await Worker(r, build_graph(InMemorySaver())).process("j1")
    assert (await r.hget(keys.job("j1"), "status")) == b"succeeded"
    types = await _types(r, "j1")
    assert types[0] == "job.started" and types[-1] == "message.completed" and "token" in types
    assert await r.llen(keys.conv_msgs("c1")) == 2


async def test_cancel_before_start():
    r = fakeredis.FakeAsyncRedis()
    await _enqueue(r)
    await r.set(keys.job_cancel("j1"), 1)
    await Worker(r, build_graph(InMemorySaver())).process("j1")
    assert (await r.hget(keys.job("j1"), "status")) == b"cancelled"
    assert await _types(r, "j1") == ["job.cancelled"]
