"""Graph test chạy thật: OpenAI + Redis DB 15 + collection Qdrant riêng (không đụng dữ liệu dev)."""

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from ai_service.agent.context import RunContext
from ai_service.agent.graph import Graph, build_graph
from ai_service.rag.retriever import Retriever

from ..integration.rag_env import KB_DIR, RagEnv

COLLECTION = "kb_chunks_test_graph"


@pytest.fixture(scope="session")
def _test_collection() -> Iterator[None]:
    """Chỉ test dùng `graph` mới cần hạ tầng → dọn collection cuối phiên (test thuần không đụng Qdrant)."""
    yield

    async def drop() -> None:
        env = RagEnv(COLLECTION)
        await env.drop()
        await env.close()

    asyncio.run(drop())


@pytest.fixture
async def graph(_test_collection: None) -> AsyncIterator[Graph]:
    env = RagEnv(COLLECTION)
    report, _ = await env.ingest(KB_DIR)  # lần đầu nạp (embedding từ cache), các test sau skip hết
    assert not report.rejected
    yield build_graph(InMemorySaver(), retriever=Retriever(env.qdrant, env.embedder(), COLLECTION))
    await env.close()


async def ask(graph: Graph, text: str, mode: str = "qa", thread: str | None = None) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread or uuid.uuid4().hex}}
    out = await graph.ainvoke(
        {"messages": [HumanMessage(text)], "requested_mode": mode},
        config,  # type: ignore[arg-type]
        context=RunContext(job_id="test", user_id="test", mode=mode),
    )
    return out["final"]
