from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.nodes._common import history, sources_block, started, system_prompt, text_of
from ai_service.agent.prompts import load_prompt
from ai_service.agent.state import AgentState
from ai_service.llm.client import chat


def question_block(state: AgentState) -> str:
    """Câu standalone (đã gộp ngữ cảnh) + tin nhắn gốc — tin gốc quyết định ngôn ngữ trả lời."""
    msgs = state.get("messages") or []
    original = text_of(msgs[-1]) if msgs else state["question"]
    return f"Question: {state['question']}\nUser's original message (reply in ITS language): {original}"


def coverage_note(state: AgentState) -> str:
    g = state.get("grade") or {}
    if g.get("status") == "partial" and g.get("missing_aspects"):
        missing = "; ".join(g["missing_aspects"])
        return (
            f"The sources do NOT cover: {missing}. Answer what the sources support and state clearly what is missing."
        )
    return "Answer completely from the sources."


async def generate_answer(state: AgentState) -> dict:
    started("generate_answer", "Đang soạn câu trả lời")
    prompt = load_prompt("answer").render(coverage=coverage_note(state), sources=sources_block(state["evidence"]))
    msgs = [
        SystemMessage(system_prompt()),
        *history(state),
        HumanMessage(f"{prompt}\n\n{question_block(state)}"),
    ]
    msg = await chat("chat-default", streaming=True).ainvoke(msgs)
    return {"draft_md": text_of(msg).strip()}
