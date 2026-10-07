"""Lớp DUY NHẤT chuyển stream của LangGraph thành event hệ thống (§8.3)."""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from ai_service.agent.context import RunContext
from ai_service.agent.graph import STREAMABLE_NODES, Graph
from ai_service.agent.state import AgentState
from ai_service.rag.ingest.manifest import Manifest
from ai_service.rag.ingest.pipeline import IngestReport, run_ingest
from ai_service.settings import settings
from ai_service.worker import jobs, step_details, store
from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys
from shared.contracts import ErrorCode, FinalPayload


@dataclass(frozen=True)
class Deps:
    redis: Redis
    graph: Graph
    qdrant: AsyncQdrantClient | None = None  # chỉ job ingest cần
    embedder: Embeddings | None = None


class JobCancelled(Exception):
    pass


class JobError(Exception):
    """Lỗi có mã rõ ràng → `job.failed {code, message}` thay vì `internal_error`."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code


class CancelCheck:
    """`EXISTS job:{id}:cancel` giữa các chunk — tối đa mỗi INTERVAL_S một lần để stream token không
    tốn một lệnh Redis cho mỗi token."""

    INTERVAL_S = 0.2

    def __init__(self, redis: Redis, job_id: str):
        self.redis, self.key = redis, keys.job_cancel(job_id)
        self._last = float("-inf")

    async def __call__(self) -> None:
        now = time.monotonic()
        if now - self._last < self.INTERVAL_S:
            return
        self._last = now
        if await self.redis.exists(self.key):
            raise JobCancelled()


async def handle_chat(deps: Deps, job: dict[str, str], pub: EventPublisher) -> None:
    inp = json.loads(job["input"])
    ctx = RunContext(job_id=job["job_id"], user_id=job["user_id"], mode=inp["mode"])
    config: RunnableConfig = {"configurable": {"thread_id": job["conversation_id"]}}
    inputs: AgentState = {"messages": [HumanMessage(inp["text"])], "requested_mode": inp["mode"]}
    check_cancel = CancelCheck(deps.redis, job["job_id"])
    started: dict[str, float] = {}  # node → thời điểm node.started
    steps: list[dict[str, Any]] = []  # lưu cùng message → mở lại hội thoại vẫn thấy các bước

    await pub.emit("job.started", {})
    part: Any
    async for part in deps.graph.astream(
        inputs,
        config,
        context=ctx,
        stream_mode=["custom", "messages", "updates"],
    ):
        mode, chunk = part  # stream_mode là list → (mode, chunk)
        if mode == "messages":
            msg, meta = chunk
            if meta.get("langgraph_node") in STREAMABLE_NODES and isinstance(msg.content, str) and msg.content:
                await pub.token(msg.content)
        elif mode == "custom":
            if chunk["type"] == "node.started":
                started[chunk["data"]["node"]] = time.monotonic()
            await pub.emit(chunk["type"], chunk["data"])
        elif mode == "updates":
            for node, update in chunk.items():
                step = _completed(node, update or {}, started.pop(node, None))
                steps.append(step)
                await pub.emit("node.completed", step)
                if node == "grade_evidence" and (update or {}).get("evidence"):
                    # grade lọc chunk + đánh số lại S1..Sn → UI phải nhận danh sách mới để [S#] khớp nguồn
                    await pub.emit("retrieval.sources", _sources(update["evidence"]))
        await check_cancel()

    state = await deps.graph.aget_state(config)
    final = FinalPayload.model_validate(state.values["final"]).model_dump(mode="json")
    await store.save_turn(deps.redis, job, final, steps)
    await pub.emit("message.completed", final)


def _completed(node: str, update: dict[str, Any], t0: float | None) -> dict[str, Any]:
    label, detail = step_details.describe(node, update)
    step: dict[str, Any] = {"node": node, "label": label, "detail": detail}
    if t0 is not None:
        step["duration_ms"] = round((time.monotonic() - t0) * 1000)
    return step


def _sources(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: e[k] for k in ("sid", "chunk_id", "title", "section", "doc_type")} for e in evidence]


async def handle_ingest(deps: Deps, job: dict[str, str], pub: EventPublisher) -> None:
    if deps.qdrant is None or deps.embedder is None:
        raise JobError("internal_error", "Worker không được cấu hình cho job ingest")
    job_id = job["job_id"]
    recreate = bool(json.loads(job["input"]).get("recreate", False))
    if not await deps.redis.set(keys.KB_INGEST_LOCK, job_id, nx=True, ex=settings.job_timeout_s + 60):
        raise JobError("validation_error", "Đang có job ingest khác chạy")
    check_cancel = CancelCheck(deps.redis, job_id)

    async def progress(source_path: str, action: str, done: int, total: int) -> None:
        await pub.emit("ingest.progress", {"source_path": source_path, "action": action, "done": done, "total": total})
        await check_cancel()  # manifest ghi theo từng tài liệu → hủy giữa chừng, lần sau làm tiếp

    await pub.emit("job.started", {})
    try:
        report = await run_ingest(
            Path(settings.kb_dir),
            qdrant=deps.qdrant,
            manifest=Manifest(deps.redis),
            embedder=deps.embedder,
            collection=settings.qdrant_collection,
            recreate=recreate,
            on_progress=progress,
        )
    finally:
        if await deps.redis.get(keys.KB_INGEST_LOCK) in (job_id, job_id.encode()):
            await deps.redis.delete(keys.KB_INGEST_LOCK)

    final = _ingest_payload(report)
    await jobs.finish(deps.redis, job, "succeeded")
    await pub.emit("message.completed", final.model_dump(mode="json"))


def _ingest_payload(report: IngestReport) -> FinalPayload:
    return FinalPayload(
        status="partial" if report.rejected else "answered",
        answer_md=f"Ingest `{settings.qdrant_collection}`: {report.summary()}",
        missing_info=[f"{path}: {err}" for path, err in report.rejected.items()],
    )


Handler = Callable[[Deps, dict[str, str], EventPublisher], Awaitable[None]]
HANDLERS: dict[str, Handler] = {"chat": handle_chat, "ingest": handle_ingest}
