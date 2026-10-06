import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from ai_service.agent.context import RunContext
from ai_service.agent.graph import build_graph


@pytest.mark.llm
async def test_graph_answers_with_citation():
    graph = build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    out = await graph.ainvoke(
        {"messages": [HumanMessage("Giá serum?")]},
        config,
        context=RunContext(job_id="j", user_id="u", mode="qa"),
    )
    final = out["final"]
    assert final["status"] == "answered"
    assert final["answer_md"]
    # model thật: chỉ kiểm tra citation (nếu có) trỏ tới evidence đã cấp
    assert all(c["sid"] == "S1" for c in final["citations"])
