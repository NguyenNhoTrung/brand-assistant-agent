"""Tiện ích dùng chung cho node: phát tiến trình, dựng prompt, lịch sử hội thoại, evidence ↔ <source>."""

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from ai_service.agent.edges import ARTIFACT_INTENTS
from ai_service.agent.prompts import load_prompt
from ai_service.agent.state import AgentState
from ai_service.compliance.rules import rules_prompt
from ai_service.rag.context_builder import Evidence, render_source

HISTORY_TURNS = 6  # §9.4: cắt lịch sử còn 6 lượt
NOSTREAM: RunnableConfig = {"tags": ["nostream"]}  # structured output / artifact: không lộ token ra stream


def emit(event_type: str, data: dict[str, Any] | list[Any]) -> None:
    """Node KHÔNG biết Redis: phát qua stream `custom`; gọi ngoài graph (unit test) → bỏ qua."""
    try:
        write = get_stream_writer()
    except RuntimeError:
        return
    write({"type": event_type, "data": data})


def started(node: str, label: str) -> None:
    emit("node.started", {"node": node, "label": label})


def text_of(msg: BaseMessage | Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)


def history(state: AgentState) -> list[AnyMessage]:
    """Các lượt TRƯỚC (không gồm câu hỏi hiện tại), tối đa HISTORY_TURNS lượt, chỉ human/AI."""
    msgs: list[AnyMessage] = [m for m in state.get("messages", [])[:-1] if isinstance(m, HumanMessage | AIMessage)]
    return msgs[-HISTORY_TURNS * 2 :]


def system_prompt() -> str:
    return load_prompt("system").render(rules=rules_prompt())


def evidence_objs(evidence: Sequence[dict[str, Any]]) -> list[Evidence]:
    return [Evidence(**e) for e in evidence]


def sources_block(evidence: Sequence[dict[str, Any]]) -> str:
    if not evidence:
        return "<sources>\n(no sources)\n</sources>"
    return "<sources>\n" + "\n\n".join(render_source(e) for e in evidence_objs(evidence)) + "\n</sources>"


def intent(state: AgentState) -> str:
    return str((state.get("route") or {}).get("intent", "qa"))


def is_artifact(state: AgentState) -> bool:
    return intent(state) in ARTIFACT_INTENTS
