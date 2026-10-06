from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # tồn tại qua nhiều lượt (checkpoint)

    # Theo từng lượt — load_context PHẢI reset
    requested_mode: str
    question: str
    evidence: list[dict[str, Any]]
    draft_md: str | None
    final: dict[str, Any]
