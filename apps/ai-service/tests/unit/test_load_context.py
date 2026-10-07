from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from ai_service.agent.context import RunContext
from ai_service.agent.nodes.load_context import MAX_MESSAGES, load_context
from ai_service.agent.state import TURN_RESET


def _runtime(mode: str = "qa") -> SimpleNamespace:
    return SimpleNamespace(context=RunContext(job_id="j", user_id="u", mode=mode))


async def test_resets_every_turn_field() -> None:
    prev_turn = {
        "messages": [HumanMessage("q1", id="1"), AIMessage("a1", id="2"), HumanMessage("q2", id="3")],
        "requested_mode": "creative_brief",
        "question": "q1",
        "route": {"intent": "creative_brief"},
        "evidence": [{"sid": "S1"}],
        "max_cosine": 0.7,
        "grade": {"status": "sufficient"},
        "draft_md": "old answer [S1]",
        "artifact": {"title": "old"},
        "verification": {"passed": False, "issues": []},
        "revision_count": 2,
        "retrieval_attempts": 2,
        "outcome": "abstained",
        "final": {"status": "answered"},
    }
    out = await load_context(prev_turn, _runtime("qa"))
    for key, value in TURN_RESET.items():
        if key != "question":
            assert out[key] == value, key
    assert out["question"] == "q2"
    assert out["requested_mode"] == "qa"  # mode của lượt mới, không mang từ lượt trước
    assert "messages" not in out  # lịch sử ngắn → không cắt


async def test_trims_history_to_six_turns() -> None:
    msgs = [HumanMessage(f"m{i}", id=str(i)) for i in range(MAX_MESSAGES + 4)]
    out = await load_context({"messages": msgs}, _runtime())
    removed = out["messages"]
    assert all(isinstance(m, RemoveMessage) for m in removed)
    assert [m.id for m in removed] == ["0", "1", "2", "3"]
