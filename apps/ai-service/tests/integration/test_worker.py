"""Worker với fakeredis — không gọi LLM/Qdrant. Graph/handler thay bằng test double trong test."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import fakeredis
import httpx
import openai
import pytest
from langchain_core.messages import AIMessageChunk
from redis.exceptions import TimeoutError as RedisTimeoutError

from ai_service.settings import settings
from ai_service.worker import handlers
from ai_service.worker.handlers import Deps, JobError
from ai_service.worker.loop import Worker
from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys
from shared.lua import Scripts

FINAL = {
    "status": "answered",
    "answer_md": "Giá $42 [1]",
    "citations": [{"n": 1, "sid": "S1", "chunk_id": "products/serum.md#0", "title": "Vitamin C Serum"}],
    "confidence": "high",
}


class FakeGraph:
    """Phát lại một chuỗi (mode, chunk) như `graph.astream(stream_mode=[...])`."""

    def __init__(self, parts: list[tuple[str, Any]], final: dict | None = None, on_part=None):
        self.parts, self.final, self.on_part = parts, final or FINAL, on_part

    async def astream(self, *_: Any, **__: Any):
        for i, p in enumerate(self.parts):
            if self.on_part:
                await self.on_part(i)
            yield p

    async def aget_state(self, _config: Any) -> SimpleNamespace:
        return SimpleNamespace(values={"final": self.final})


def _tok(text: str, node: str) -> tuple[str, Any]:
    return ("messages", (AIMessageChunk(content=text), {"langgraph_node": node}))


PARTS: list[tuple[str, Any]] = [
    ("custom", {"type": "node.started", "data": {"node": "route", "label": "Phân loại câu hỏi"}}),
    ("custom", {"type": "route.decided", "data": {"intent": "qa", "doc_types": ["product"]}}),
    ("updates", {"route": {}}),
    _tok('{"intent":', "route"),  # structured output của node khác → không lộ ra token
    _tok("Giá ", "generate_answer"),
    _tok("$42 [S1]", "generate_answer"),
    ("updates", {"generate_answer": {}}),
]

EV = {"source_path": "products/serum.md", "chunk_id": "products/serum.md#0", "title": "Serum", "section": "Price"}


def _ev(*sids: str) -> list[dict]:
    return [{**EV, "sid": sid, "doc_type": "product"} for sid in sids]


async def test_node_completed_has_result_label_and_steps_are_saved(r):
    parts: list[tuple[str, Any]] = [
        ("custom", {"type": "node.started", "data": {"node": "retrieve", "label": "Đang tìm"}}),
        ("updates", {"retrieve": {"evidence": _ev("S1", "S2", "S3")}}),
        ("updates", {"grade_evidence": {"grade": {"status": "sufficient"}, "evidence": _ev("S1")}}),
        ("updates", {"verify": {"verification": {"passed": True, "issues": []}}}),
    ]
    await _enqueue(r)
    await _worker(r, FakeGraph(parts)).process("j1")
    events = await _events(r)
    done = [d for t, d in events if t == "node.completed"]
    assert done[0]["label"] == "Tìm thấy 3 đoạn từ 1 tài liệu" and "duration_ms" in done[0]
    assert done[1]["label"] == "Bằng chứng: đủ · giữ 1 đoạn"
    assert done[2]["label"] == "Kiểm tra compliance & trích dẫn: đạt"
    # grade đánh số lại → danh sách nguồn mới được phát ngay sau bước grade
    types = [t for t, _ in events]
    assert types[types.index("retrieval.sources") - 1] == "node.completed"
    assert [s["sid"] for t, d in events if t == "retrieval.sources" for s in d] == ["S1"]
    ai_id = (await r.get(keys.job_msg("j1"))).decode()
    saved = json.loads(await r.get(keys.msg(ai_id)))["steps"]
    assert [s["node"] for s in saved] == ["retrieve", "grade_evidence", "verify"]


@pytest.fixture
def r() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis()


async def _enqueue(r, job_id="j1", job_type="chat", inp=None):
    await Scripts(r).create_job(
        job_id=job_id,
        user_id="u1",
        conversation_id="c1",
        idem_key=f"k-{job_id}",
        input_json=json.dumps(inp or {"text": "Giá serum?", "mode": "qa"}),
        now_ms=1,
        job_type=job_type,
        title="t",
    )


async def _events(r, job_id="j1") -> list[tuple[str, Any]]:
    return [
        (e[1][b"type"].decode(), json.loads(e[1][b"data"])["data"]) for e in await r.xrange(keys.job_events(job_id))
    ]


async def _types(r, job_id="j1") -> list[str]:
    return [t for t, _ in await _events(r, job_id)]


async def _status(r, job_id="j1") -> str:
    return (await r.hget(keys.job(job_id), "status")).decode()


def _worker(r, graph=None, **deps) -> Worker:
    return Worker(Deps(r, graph or FakeGraph(PARTS), **deps))


async def test_chat_job_streams_events_and_saves_turn(r):
    await _enqueue(r)
    await _worker(r).process("j1")

    assert await _status(r) == "succeeded"
    events = await _events(r)
    assert [t for t, _ in events] == [
        "job.started",
        "node.started",
        "route.decided",
        "node.completed",
        "token",
        "node.completed",
        "message.completed",
    ]
    completed = dict(events)["node.completed"]
    assert {"node", "label", "duration_ms"} <= set(events[3][1]) and completed["node"] == "generate_answer"
    assert dict(events)["token"]["delta"] == "Giá $42 [S1]"
    assert dict(events)["message.completed"]["citations"][0]["chunk_id"] == "products/serum.md#0"

    _user_id, ai_id = [m.decode() for m in await r.lrange(keys.conv_msgs("c1"), 0, -1)]
    ai = json.loads(await r.get(keys.msg(ai_id)))
    assert ai["role"] == "assistant" and ai["content_md"] == "Giá $42 [1]"
    assert ai["citations"][0]["n"] == 1 and ai["confidence"] == "high" and ai["missing_info"] == []
    assert (await r.get(keys.job_msg("j1"))).decode() == ai_id
    assert await r.hget(keys.conv("c1"), "active_job_id") == b""


async def test_job_not_queued_is_skipped(r):
    await _enqueue(r)
    await r.hset(keys.job("j1"), "status", "running")  # worker khác đã nhận
    await _worker(r).process("j1")
    assert await _status(r) == "running"
    assert await _types(r) == []


async def test_missing_job_is_skipped(r):
    await _worker(r).process("không-tồn-tại")
    assert await r.keys("*") == []


async def test_cancel_before_start(r):
    await _enqueue(r)
    await r.set(keys.job_cancel("j1"), 1)
    await _worker(r).process("j1")
    assert await _status(r) == "cancelled"
    assert await _types(r) == ["job.cancelled"]
    assert await r.hget(keys.conv("c1"), "active_job_id") == b""


async def test_cancel_mid_stream(r, monkeypatch):
    async def cancel_at_token(i: int) -> None:
        if i == 4:
            await r.set(keys.job_cancel("j1"), 1)

    monkeypatch.setattr(handlers.CancelCheck, "INTERVAL_S", 0)  # kiểm tra mỗi chunk → deterministic
    await _enqueue(r)
    await _worker(r, FakeGraph(PARTS, on_part=cancel_at_token)).process("j1")
    assert await _status(r) == "cancelled"
    types = await _types(r)
    assert types[-1] == "job.cancelled" and "message.completed" not in types
    assert await r.llen(keys.conv_msgs("c1")) == 0


def _openai_error(cls: type[openai.APIStatusError]) -> openai.APIStatusError:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return cls("x", response=httpx.Response(429, request=req), body=None)


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (RuntimeError("boom"), "internal_error"),
        (JobError("validation_error", "sai input"), "validation_error"),
        (_openai_error(openai.RateLimitError), "llm_unavailable"),
        (openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com")), "llm_unavailable"),
    ],
)
async def test_handler_error_marks_failed(r, monkeypatch, exc, code):
    async def boom(*_: Any) -> None:
        raise exc

    monkeypatch.setitem(handlers.HANDLERS, "chat", boom)
    await _enqueue(r)
    await _worker(r).process("j1")
    assert await _status(r) == "failed"
    assert json.loads(await r.hget(keys.job("j1"), "error"))["code"] == code
    (t, data), *_ = await _events(r)
    assert t == "job.failed" and data["code"] == code
    assert await r.ttl(keys.job_events("j1")) > 0
    assert await r.hget(keys.conv("c1"), "active_job_id") == b""


async def test_timeout_marks_job_timeout(r, monkeypatch):
    async def slow(*_: Any) -> None:
        await asyncio.sleep(10)

    monkeypatch.setitem(handlers.HANDLERS, "chat", slow)
    monkeypatch.setattr(settings, "job_timeout_s", 0.05)
    await _enqueue(r)
    await _worker(r).process("j1")
    assert await _status(r) == "failed"
    assert await _events(r) == [("job.failed", {"code": "job_timeout", "message": "Job vượt quá thời gian cho phép"})]


async def test_shutdown_interrupts_long_job(r, monkeypatch):
    running = asyncio.Event()

    async def hang(*_: Any) -> None:
        running.set()
        await asyncio.sleep(60)

    monkeypatch.setitem(handlers.HANDLERS, "chat", hang)
    monkeypatch.setattr(settings, "worker_concurrency", 1)
    monkeypatch.setattr(settings, "shutdown_grace_s", 0.1)
    await _enqueue(r)
    worker = _worker(r)
    task = asyncio.create_task(worker.run())
    await asyncio.wait_for(running.wait(), 5)
    worker.stopping.set()
    await asyncio.wait_for(task, 5)
    assert await _status(r) == "failed"
    assert (await _events(r))[-1] == ("job.failed", {"code": "job_timeout", "message": "Worker dừng khi job đang chạy"})


async def test_each_job_runs_once_across_workers(r, monkeypatch):
    seen: list[str] = []

    async def record(_deps: Deps, job: dict[str, str], pub: EventPublisher) -> None:
        seen.append(job["job_id"])
        await asyncio.sleep(0.01)
        await r.hset(keys.job(job["job_id"]), "status", "succeeded")

    monkeypatch.setitem(handlers.HANDLERS, "chat", record)
    monkeypatch.setattr(settings, "worker_concurrency", 3)
    for i in range(6):
        await _enqueue(r, job_id=f"j{i}")
    workers = [_worker(r), _worker(r)]
    tasks = [asyncio.create_task(w.run()) for w in workers]
    for _ in range(200):
        if await r.llen(keys.QUEUE) == 0 and len(seen) == 6:
            break
        await asyncio.sleep(0.01)
    for w in workers:
        w.stopping.set()
    await asyncio.wait_for(asyncio.gather(*tasks), 10)
    assert sorted(seen) == [f"j{i}" for i in range(6)]


async def test_ingest_job_reports_progress(r, monkeypatch):
    async def fake_ingest(kb_dir, *, on_progress, recreate, **_):
        assert recreate is True
        await on_progress("products/a.md", "added", 1, 2)
        await on_progress("products/b.md", "skipped", 2, 2)
        report = handlers.IngestReport(added=["products/a.md"], skipped=["products/b.md"], chunks_written=3)
        return report

    monkeypatch.setattr(handlers, "run_ingest", fake_ingest)
    await _enqueue(r, job_type="ingest", inp={"text": "ingest", "mode": "auto", "recreate": True})
    await _worker(r, qdrant=object(), embedder=object()).process("j1")

    assert await _status(r) == "succeeded"
    events = await _events(r)
    assert [t for t, _ in events] == ["job.started", "ingest.progress", "ingest.progress", "message.completed"]
    assert events[1][1] == {"source_path": "products/a.md", "action": "added", "done": 1, "total": 2}
    assert "added=1" in events[-1][1]["answer_md"]
    assert not await r.exists(keys.KB_INGEST_LOCK)


async def test_ingest_rejects_concurrent_run(r):
    await r.set(keys.KB_INGEST_LOCK, "other-job")
    await _enqueue(r, job_type="ingest", inp={"text": "ingest", "mode": "auto"})
    await _worker(r, qdrant=object(), embedder=object()).process("j1")
    assert await _status(r) == "failed"
    assert (await _events(r))[-1][1]["code"] == "validation_error"
    assert (await r.get(keys.KB_INGEST_LOCK)) == b"other-job"


async def test_loop_survives_redis_errors(r, monkeypatch):
    """Lỗi BRPOP (Redis restart, timeout socket) không được giết task vòng lặp."""
    calls = 0
    real_brpop = r.brpop

    async def flaky_brpop(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RedisTimeoutError("Timeout reading from redis")
        return await real_brpop(*args, **kwargs)

    monkeypatch.setattr(r, "brpop", flaky_brpop)
    await _enqueue(r)
    worker = _worker(r)
    loop_task = asyncio.create_task(worker.loop())
    for _ in range(300):  # lần BRPOP lỗi → worker nghỉ 1s rồi thử lại
        if await _status(r) == "succeeded":
            break
        await asyncio.sleep(0.01)
    worker.stopping.set()
    await asyncio.wait_for(loop_task, 5)
    assert await _status(r) == "succeeded" and calls >= 2
