import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.nodes._common import NOSTREAM, history, intent, is_artifact, started
from ai_service.agent.prompts import load_prompt
from ai_service.agent.schemas import RetrievalPlan, RetrievalQuery
from ai_service.agent.state import AgentState
from ai_service.llm.client import structured
from ai_service.skills.registry import get_skill

log = structlog.get_logger()
MAX_LLM_QUERIES = 3


async def plan_retrieval(state: AgentState) -> dict:
    started("plan_retrieval", "Đang lập kế hoạch tìm kiếm")
    question = state["question"]
    msgs = [SystemMessage(load_prompt("plan").text), *history(state), HumanMessage(question)]
    try:
        plan = await structured("chat-fast", RetrievalPlan).ainvoke(msgs, config=NOSTREAM)
        assert isinstance(plan, RetrievalPlan) and plan.queries
    except Exception as e:
        log.warning("plan_retrieval.failed", error=str(e))
        plan = RetrievalPlan(
            question=question,
            queries=[RetrievalQuery(text=question, text_en=question, doc_types=[])],
            product=None,
            channel=None,
            category=None,
        )

    standalone = plan.question.strip() or question
    queries = plan.queries[:MAX_LLM_QUERIES]
    # Luôn có 1 truy vấn KHÔNG lọc doc_type: LLM lọc sai không được làm mất bằng chứng
    if all(q.doc_types for q in queries):
        queries.append(RetrievalQuery(text=standalone, text_en=queries[0].text_en, doc_types=[]))
    slots = {"product": plan.product, "channel": plan.channel, "category": plan.category}
    if is_artifact(state) and (skill := get_skill(intent(state))):
        queries += [
            RetrievalQuery.model_validate({"text": q, "text_en": q, "doc_types": list(dts)})
            for q, dts in skill.queries(slots)
        ]

    return {"question": standalone, "queries": [q.model_dump() for q in queries], "plan_slots": slots}
