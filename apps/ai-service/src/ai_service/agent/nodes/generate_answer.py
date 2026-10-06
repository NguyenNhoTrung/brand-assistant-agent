from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.state import AgentState
from ai_service.llm.client import chat

SYSTEM = "Chỉ trả lời dựa trên các <source>. Gắn [S#] sau mỗi khẳng định."  # TODO: prompts/answer.md


async def generate_answer(state: AgentState) -> dict:
    sources = "\n".join(f'<source id="{e["sid"]}">{e["text"]}</source>' for e in state["evidence"])
    msg = await chat("chat-default", streaming=True).ainvoke(
        [SystemMessage(SYSTEM), HumanMessage(f"{sources}\n\nCâu hỏi: {state['question']}")]
    )
    return {"draft_md": msg.content, "messages": [msg]}
