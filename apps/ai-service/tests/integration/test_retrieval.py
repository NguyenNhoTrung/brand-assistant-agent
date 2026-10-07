"""Hybrid retrieval trên toàn bộ KB: `expected_sources` của golden set phải nằm trong top-5."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from ai_service.rag.retriever import RetrievalQuery, Retriever

from .rag_env import KB_DIR, RagEnv

pytestmark = [pytest.mark.infra, pytest.mark.llm]

COLLECTION = "kb_chunks_test_retrieval"
GOLDEN = Path(__file__).resolve().parents[4] / "evals" / "golden_set.jsonl"
CASES = ["qa-001", "qa-003", "qa-006", "qa-009", "con-001"]  # giá · creative · SOP · câu tiếng Việt · mâu thuẫn


def _golden() -> dict[str, dict]:
    rows = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]
    return {r["id"]: r for r in rows}


@pytest.fixture(scope="module", autouse=True)
def _cleanup() -> Iterator[None]:
    yield

    async def drop() -> None:
        env = RagEnv(COLLECTION)
        await env.drop()
        await env.close()

    asyncio.run(drop())


@pytest.fixture
async def retriever() -> AsyncIterator[Retriever]:
    env = RagEnv(COLLECTION)
    report, _ = await env.ingest(KB_DIR)  # lần đầu nạp; các test sau skip hết (idempotent)
    assert not report.rejected
    yield Retriever(env.qdrant, env.embedder(), COLLECTION)
    await env.close()


@pytest.mark.parametrize("case_id", CASES)
async def test_expected_sources_in_top5(retriever: Retriever, case_id: str) -> None:
    case = _golden()[case_id]
    res = await retriever.hybrid_search(RetrievalQuery(case["q"]), k=5)
    top5 = [c.source_path for c in res.chunks]
    for src in case["expected_sources"]:
        assert src in top5, f"{case_id}: {src} không có trong top-5 {top5}"
    assert "products/vitamin-c-serum-2025.md" not in top5


async def test_search_many_merges_and_dedups(retriever: Retriever) -> None:
    res = await retriever.search_many(
        [RetrievalQuery("Vitamin C Serum price"), RetrievalQuery("vitamin c serum cost"), RetrievalQuery("SPF 50")],
        k=8,
    )
    ids = [c.chunk_id for c in res.chunks]
    assert len(ids) == len(set(ids))
    paths = {c.source_path for c in res.chunks}
    assert {"products/vitamin-c-serum.md", "products/spf50-daily-fluid.md"} <= paths


async def test_max_cosine_lower_for_out_of_scope(retriever: Retriever) -> None:
    in_scope = await retriever.hybrid_search(RetrievalQuery("What is the price of the Vitamin C Serum?"))
    off = await retriever.hybrid_search(RetrievalQuery("What's the weather in Paris tomorrow?"))
    assert 0 < off.max_cosine < in_scope.max_cosine
