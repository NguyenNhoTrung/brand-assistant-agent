from ai_service.agent.nodes._common import started
from ai_service.agent.state import AgentState

OUT_OF_SCOPE = (
    "Mình là trợ lý kiến thức nội bộ của Lumi Botanics — mình chỉ trả lời dựa trên knowledge base của công ty "
    "(sản phẩm, brand guideline, compliance, SOP, customer research, creative learnings) và soạn creative brief. "
    "Câu hỏi này nằm ngoài phạm vi đó."
)
CLARIFY = "Bạn có thể nói rõ hơn bạn cần gì không (sản phẩm nào, kênh nào, loại nội dung nào)?"


async def respond_direct(state: AgentState) -> dict:
    started("respond_direct", "Đang phản hồi")
    r = state["route"]
    if r.get("needs_clarification"):
        return {"outcome": "clarification", "draft_md": r.get("clarification_question") or CLARIFY}
    return {"outcome": "out_of_scope", "draft_md": OUT_OF_SCOPE}
