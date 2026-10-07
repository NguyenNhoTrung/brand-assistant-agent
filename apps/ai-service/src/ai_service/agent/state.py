"""State của graph (§9.3). Giá trị là dict/JSON thuần (model_dump) → checkpoint Redis serialize an toàn.

Chỉ `messages` tồn tại qua nhiều lượt; mọi field còn lại là của MỘT lượt — `load_context` reset (xem `TURN_RESET`).
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Outcome = Literal["clarification", "out_of_scope", "abstained"]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # tồn tại qua nhiều lượt (checkpoint)

    # Theo từng lượt
    requested_mode: str
    question: str  # câu hỏi standalone (plan_retrieval gộp ngữ cảnh hội thoại)
    route: dict[str, Any]  # RouteDecision
    queries: list[dict[str, Any]]  # RetrievalQuery
    plan_slots: dict[str, str | None]  # product / channel / category cho retrieval plan của skill
    retrieval_attempts: int
    evidence: list[dict[str, Any]]  # Evidence.as_dict(), sid "S1".."Sn"
    max_cosine: float
    grade: dict[str, Any]  # EvidenceGrade
    draft_md: str | None
    artifact: dict[str, Any] | None
    verification: dict[str, Any] | None  # VerificationReport
    revision_count: int
    outcome: Outcome | None  # respond_direct / abstain đặt; None = đi đường sinh câu trả lời
    abstain: dict[str, Any] | None  # AbstainNote
    final: dict[str, Any]  # FinalPayload


TURN_RESET: AgentState = {
    "question": "",
    "route": {},
    "queries": [],
    "plan_slots": {},
    "retrieval_attempts": 0,
    "evidence": [],
    "max_cosine": 0.0,
    "grade": {},
    "draft_md": None,
    "artifact": None,
    "verification": None,
    "revision_count": 0,
    "outcome": None,
    "abstain": None,
    "final": {},
}
