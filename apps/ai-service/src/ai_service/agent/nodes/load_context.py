from langchain_core.messages import RemoveMessage
from langgraph.runtime import Runtime

from ai_service.agent.context import RunContext
from ai_service.agent.nodes._common import HISTORY_TURNS, text_of
from ai_service.agent.state import TURN_RESET, AgentState
from ai_service.compliance.rules import load_rules

MAX_MESSAGES = HISTORY_TURNS * 2 + 1  # 6 lượt trước + câu hỏi hiện tại


async def load_context(state: AgentState, runtime: Runtime[RunContext] | None = None) -> dict:
    """Reset MỌI field theo lượt (checkpoint mang giá trị lượt trước sang), nạp rules (cache), cắt lịch sử."""
    load_rules()  # cache + fail fast nếu rules.yaml hỏng
    msgs = state.get("messages", [])
    mode = (runtime.context.mode if runtime and runtime.context else None) or state.get("requested_mode") or "auto"
    old = [RemoveMessage(id=m.id) for m in msgs[:-MAX_MESSAGES] if m.id]
    return {
        **TURN_RESET,
        "requested_mode": mode,
        "question": text_of(msgs[-1]) if msgs else "",
        **({"messages": old} if old else {}),
    }
