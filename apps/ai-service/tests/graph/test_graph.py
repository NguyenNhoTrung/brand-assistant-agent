import pytest

from ai_service.agent.graph import Graph, build_graph

from .conftest import ask

EXPECTED_NODES = {
    "load_context",
    "route",
    "respond_direct",
    "plan_retrieval",
    "retrieve",
    "grade_evidence",
    "generate_answer",
    "generate_artifact",
    "verify",
    "revise",
    "abstain",
    "finalize",
}


class _NoSearch:
    async def search_many(self, queries, k=8):
        raise AssertionError("không được gọi")


def test_graph_has_all_twelve_nodes() -> None:
    g = build_graph(retriever=_NoSearch())
    assert set(g.get_graph().nodes) - {"__start__", "__end__"} == EXPECTED_NODES


@pytest.mark.llm
@pytest.mark.infra
async def test_graph_answers_with_citation(graph: Graph) -> None:
    final = await ask(graph, "Giá serum vitamin C bao nhiêu?")
    assert final["status"] in {"answered", "partial"}
    assert final["citations"] and final["citations"][0]["n"] == 1
    assert "[1]" in final["answer_md"]


@pytest.mark.llm
async def test_out_of_scope_responds_directly() -> None:
    final = await ask(build_graph(retriever=_NoSearch()), "What's the weather in Paris tomorrow?", mode="auto")
    assert final["status"] == "out_of_scope"
    assert final["citations"] == []
