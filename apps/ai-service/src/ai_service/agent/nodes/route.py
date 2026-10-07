import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.edges import ARTIFACT_INTENTS
from ai_service.agent.nodes._common import NOSTREAM, emit, history, started
from ai_service.agent.prompts import load_prompt
from ai_service.agent.schemas import RouteDecision
from ai_service.agent.state import AgentState
from ai_service.llm.client import structured
from ai_service.skills.registry import get_skill

log = structlog.get_logger()


async def route(state: AgentState) -> dict:
    started("route", "Đang phân loại yêu cầu")
    mode = state.get("requested_mode") or "auto"
    msgs = [SystemMessage(load_prompt("route").text), *history(state), HumanMessage(state["question"])]
    try:
        decision = await structured("chat-fast", RouteDecision).ainvoke(msgs, config=NOSTREAM)
        assert isinstance(decision, RouteDecision)
    except Exception as e:
        log.warning("route.failed", error=str(e))
        decision = RouteDecision(
            intent="qa", doc_types=[], product_refs=[], needs_clarification=False, clarification_question=None
        )

    if mode != "auto":  # người dùng đã chọn chế độ → chỉ lấy doc_types / product_refs từ LLM
        decision.intent = mode  # type: ignore[assignment]
        decision.needs_clarification, decision.clarification_question = False, None
    if decision.intent in ARTIFACT_INTENTS and get_skill(decision.intent) is None:
        log.info("route.skill_missing", intent=decision.intent)
        decision.intent = "qa"  # skill chưa cài → trả lời dạng Q&A

    emit("route.decided", {"intent": decision.intent, "doc_types": decision.doc_types})
    return {"route": decision.model_dump()}
