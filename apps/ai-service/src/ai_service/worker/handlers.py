"""Lớp DUY NHẤT chuyển stream của LangGraph thành event hệ thống."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from redis.asyncio import Redis

from ai_service.agent.context import RunContext
from ai_service.agent.graph import STREAMABLE_NODES, Graph
from ai_service.agent.state import AgentState
from ai_service.worker import store
from ai_service.worker.publisher import EventPublisher
from shared import redis_keys as keys


class JobCancelled(Exception):
    pass


async def handle_chat(redis: Redis, graph: Graph, job: dict[str, str], pub: EventPublisher) -> None:
    inp = json.loads(job["input"])
    ctx = RunContext(job_id=job["job_id"], user_id=job["user_id"], mode=inp["mode"])
    config: RunnableConfig = {"configurable": {"thread_id": job["conversation_id"]}}
    inputs: AgentState = {"messages": [HumanMessage(inp["text"])], "requested_mode": inp["mode"]}

    await pub.emit("job.started", {})
    part: Any
    async for part in graph.astream(
        inputs,
        config,
        context=ctx,
        stream_mode=["custom", "messages", "updates"],
    ):
        mode, chunk = part  # stream_mode là list → (mode, chunk)
        if mode == "messages":
            msg, meta = chunk
            if meta.get("langgraph_node") in STREAMABLE_NODES and msg.content:
                await pub.token(msg.content)
        elif mode == "custom":
            await pub.emit(chunk["type"], chunk["data"])
        elif mode == "updates":
            for node in chunk:
                await pub.emit("node.completed", {"node": node})
        if await redis.exists(keys.job_cancel(job["job_id"])):
            raise JobCancelled()

    final = (await graph.aget_state(config)).values["final"]
    await store.save_turn(redis, job, final)
    await pub.emit("message.completed", final)


async def handle_ingest(redis: Redis, graph: Graph, job: dict[str, str], pub: EventPublisher) -> None:
    raise NotImplementedError("TODO(P1): chạy rag.ingest.pipeline, phát tiến độ")


Handler = Callable[[Redis, Graph, dict[str, str], EventPublisher], Awaitable[None]]
HANDLERS: dict[str, Handler] = {"chat": handle_chat, "ingest": handle_ingest}
