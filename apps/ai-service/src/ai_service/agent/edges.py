"""Hàm định tuyến — hàm THUẦN trên state (§9.5) → test bằng state dựng tay."""

from ai_service.agent.state import AgentState

MAX_RETRIEVAL_ATTEMPTS = 2
MAX_REVISIONS = 2
ARTIFACT_INTENTS = {"creative_brief", "insight_summary", "campaign_recommendation", "compliance_review"}


def after_route(s: AgentState) -> str:
    r = s["route"]
    return "respond_direct" if r["intent"] == "out_of_scope" or r.get("needs_clarification") else "plan_retrieval"


def after_grade(s: AgentState) -> str:
    g = s["grade"]
    if g["status"] == "insufficient":
        can_retry = s.get("retrieval_attempts", 0) < MAX_RETRIEVAL_ATTEMPTS and g.get("rewrite_query")
        return "retrieve" if can_retry else "abstain"  # grade_evidence đã set queries=[rewrite_query]
    return "generate_artifact" if s["route"]["intent"] in ARTIFACT_INTENTS else "generate_answer"


def after_verify(s: AgentState) -> str:
    v = s["verification"] or {}
    if v.get("passed") or s.get("revision_count", 0) >= MAX_REVISIONS:
        return "finalize"  # vẫn fail → final.status = "needs_review" (nếu còn lỗi block)
    return "revise"
