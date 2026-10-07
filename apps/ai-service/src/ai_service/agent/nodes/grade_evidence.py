from typing import Literal

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.edges import MAX_RETRIEVAL_ATTEMPTS
from ai_service.agent.nodes._common import NOSTREAM, intent, is_artifact, sources_block, started
from ai_service.agent.prompts import load_prompt
from ai_service.agent.schemas import EvidenceGrade
from ai_service.agent.state import AgentState
from ai_service.llm.client import structured
from ai_service.skills.registry import get_skill

GradeStatus = Literal["sufficient", "partial", "insufficient"]

log = structlog.get_logger()

MIN_COSINE = 0.30  # §12: dưới ngưỡng → coi như không có bằng chứng, bỏ qua LLM grading
SUFFICIENT_COSINE = 0.45  # chỉ dùng khi LLM grading lỗi


def renumber(evidence: list[dict], keep: list[str]) -> tuple[list[dict], dict[str, str]]:
    """Giữ evidence có sid trong `keep` (theo thứ hạng gốc), đánh lại S1..Sn liên tục → (evidence mới, sid cũ→mới)."""
    wanted = set(keep)
    kept = [e for e in evidence if e["sid"] in wanted]
    mapping = {e["sid"]: f"S{i}" for i, e in enumerate(kept, start=1)}
    return [{**e, "sid": mapping[e["sid"]]} for e in kept], mapping


def _fallback(max_cosine: float, sids: list[str]) -> EvidenceGrade:
    status: GradeStatus = "sufficient" if max_cosine >= SUFFICIENT_COSINE else "partial"
    return EvidenceGrade(status=status, relevant_sids=sids, covered_aspects=[], missing_aspects=[], rewrite_query=None)


def _artifact_grade(state: AgentState) -> EvidenceGrade:
    """Artifact: đánh giá deterministic theo độ phủ doc_type của skill — phần thiếu vào `open_questions`."""
    skill = get_skill(intent(state))
    evidence = state.get("evidence", [])
    have = {e["doc_type"] for e in evidence}
    missing = [dt for dt in (skill.doc_types if skill else []) if dt not in have]
    status: GradeStatus = "insufficient" if not evidence else "partial" if missing else "sufficient"
    return EvidenceGrade(
        status=status,
        relevant_sids=[e["sid"] for e in evidence],
        covered_aspects=sorted(have),
        missing_aspects=[f"no {dt} documents found" for dt in missing],
        rewrite_query=None,
    )


async def grade_evidence(state: AgentState) -> dict:
    started("grade_evidence", "Đang đánh giá bằng chứng")
    evidence = state.get("evidence", [])
    max_cosine = state.get("max_cosine", 0.0)

    if not evidence or max_cosine < MIN_COSINE:
        grade = EvidenceGrade(
            status="insufficient",
            relevant_sids=[],
            covered_aspects=[],
            missing_aspects=["no relevant documents in the knowledge base"],
            rewrite_query=None,
        )
    elif is_artifact(state):
        grade = _artifact_grade(state)
    else:
        msgs = [
            SystemMessage(load_prompt("grade").text),
            HumanMessage(f"{sources_block(evidence)}\n\nQuestion: {state['question']}"),
        ]
        try:
            g = await structured("chat-fast", EvidenceGrade).ainvoke(msgs, config=NOSTREAM)
            assert isinstance(g, EvidenceGrade)
            grade = g
        except Exception as e:
            log.warning("grade_evidence.failed", error=str(e))
            grade = _fallback(max_cosine, [e["sid"] for e in evidence])

    out: dict = {}
    valid = [s for s in grade.relevant_sids if any(e["sid"] == s for e in evidence)]
    if valid:  # lọc chunk không liên quan + đánh số lại; rỗng → giữ nguyên (đừng mất hết bằng chứng)
        out["evidence"], mapping = renumber(evidence, valid)
        grade.relevant_sids = [mapping[s] for s in dict.fromkeys(valid)]
    if grade.status != "insufficient":
        grade.rewrite_query = None
    elif grade.rewrite_query and state.get("retrieval_attempts", 0) < MAX_RETRIEVAL_ATTEMPTS:
        out["queries"] = [{"text": grade.rewrite_query, "text_en": grade.rewrite_query, "doc_types": []}]
    out["grade"] = grade.model_dump()
    return out
