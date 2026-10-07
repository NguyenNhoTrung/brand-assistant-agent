"""Worker chạy graph thật: OpenAI + Qdrant (collection riêng) + Redis DB 15 cho embedding cache.
Queue/event/message dùng fakeredis để không đụng dữ liệu dev."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator

import fakeredis
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ai_service.agent.graph import build_graph
from ai_service.rag.retriever import Retriever
from ai_service.worker.handlers import Deps
from ai_service.worker.loop import Worker
from shared import redis_keys as keys
from shared.lua import Scripts

from .rag_env import KB_DIR, RagEnv

pytestmark = [pytest.mark.llm, pytest.mark.infra]

COLLECTION = "kb_chunks_test_worker"


@pytest.fixture(scope="module")
def _test_collection() -> Iterator[None]:
    yield

    async def drop() -> None:
        env = RagEnv(COLLECTION)
        await env.drop()
        await env.close()

    asyncio.run(drop())


@pytest.fixture
async def worker(_test_collection: None) -> AsyncIterator[Worker]:
    env = RagEnv(COLLECTION)
    await env.ingest(KB_DIR)
    graph = build_graph(InMemorySaver(), retriever=Retriever(env.qdrant, env.embedder(), COLLECTION))
    yield Worker(Deps(fakeredis.FakeAsyncRedis(), graph))
    await env.close()


async def _enqueue(r, text: str, mode: str, job_id: str = "j1") -> None:
    await Scripts(r).create_job(
        job_id=job_id,
        user_id="u1",
        conversation_id="c1",
        idem_key=f"k-{job_id}",
        input_json=json.dumps({"text": text, "mode": mode}),
        now_ms=1,
        job_type="chat",
        title="t",
    )


async def _types(r, job_id: str = "j1") -> list[str]:
    return [e[1][b"type"].decode() for e in await r.xrange(keys.job_events(job_id))]


async def test_qa_job_runs_to_succeeded(worker: Worker):
    r = worker.redis
    await _enqueue(r, "How much is the Vitamin C Serum?", "qa")
    await worker.process("j1")

    assert (await r.hget(keys.job("j1"), "status")) == b"succeeded"
    types = await _types(r)
    assert types[0] == "job.started" and types[-1] == "message.completed" and "token" in types
    assert {"route.decided", "retrieval.sources", "verification.result", "node.completed"} <= set(types)
    assert types.index("retrieval.sources") < types.index("token")

    ai_id = (await r.get(keys.job_msg("j1"))).decode()
    ai = json.loads(await r.get(keys.msg(ai_id)))
    assert ai["status"] in {"answered", "partial"} and ai["citations"] and ai["confidence"]
    assert "$42" in ai["content_md"]
    assert await r.llen(keys.conv_msgs("c1")) == 2


async def test_artifact_job_does_not_stream_tokens(worker: Worker):
    r = worker.redis
    await _enqueue(r, "Creative brief for SPF 50 Daily Fluid on Instagram Reels", "creative_brief")
    await worker.process("j1")
    types = await _types(r)
    assert types[-1] == "message.completed" and "artifact.ready" in types
    assert "token" not in types  # §7.4: artifact không lộ bản nháp chưa verify


async def test_cancel_mid_run(worker: Worker):
    r = worker.redis
    await _enqueue(r, "Creative brief for SPF 50 Daily Fluid on Instagram Reels", "creative_brief")

    async def cancel_when_retrieved() -> None:
        while "retrieval.sources" not in await _types(r):  # noqa: ASYNC110 — event nằm trong Redis
            await asyncio.sleep(0.05)
        await r.set(keys.job_cancel("j1"), 1)

    canceller = asyncio.create_task(cancel_when_retrieved())
    await worker.process("j1")
    await canceller
    assert (await r.hget(keys.job("j1"), "status")) == b"cancelled"
    types = await _types(r)
    assert types[-1] == "job.cancelled" and "message.completed" not in types
    assert await r.llen(keys.conv_msgs("c1")) == 0
