"""finalize: deterministic — status, resolve citation `[S#]` → `[n]`, confidence, compliance summary (§9.4)."""

from langchain_core.messages import AIMessage

from ai_service.agent.confidence import confidence
from ai_service.agent.nodes._common import emit, intent, is_artifact
from ai_service.agent.schemas import Citation, ComplianceSummary, FinalPayload, Issue, VerificationReport
from ai_service.agent.state import AgentState
from ai_service.rag.citations import resolve_citations
from ai_service.skills.registry import get_skill

_SPLIT = "\n\n<<<ARTIFACT>>>\n\n"  # resolve câu trả lời + artifact chung một lượt → số [n] thống nhất


def artifact_summary(artifact: dict) -> str:
    lines = [f"Đã soạn **{artifact.get('title', 'artifact')}** — xem chi tiết ở panel artifact."]
    notes = artifact.get("compliance_notes") or []
    if notes:
        lines.append("\n**Lưu ý compliance — không dùng các claim sau:**")
        for n in notes:
            exp = n.get("explanation") or {}
            cites = "".join(f"[{s}]" for s in exp.get("source_ids", []))
            alts = " · ".join(f'"{a}"' for a in n.get("compliant_alternatives", []))
            lines.append(f'- **{n.get("rule_id")}** — "{n.get("requested_claim")}": {exp.get("text", "")} {cites}')
            if alts:
                lines.append(f"  - Phương án hợp lệ: {alts}")
    if artifact.get("open_questions"):
        lines.append("\n**Còn thiếu trong knowledge base:**")
        lines += [f"- {q}" for q in artifact["open_questions"]]
    return "\n".join(lines)


def _status(state: AgentState, report: VerificationReport | None) -> str:
    if state.get("outcome"):
        return str(state["outcome"])
    if report and report.blocking:
        return "needs_review"  # hết lượt revise mà còn lỗi block
    return "partial" if (state.get("grade") or {}).get("status") == "partial" else "answered"


async def finalize(state: AgentState) -> dict:
    report = VerificationReport.model_validate(state["verification"]) if state.get("verification") else None
    status = _status(state, report)
    artifact = state.get("artifact") if is_artifact(state) and not state.get("outcome") else None
    skill = get_skill(intent(state)) if artifact else None

    answer = artifact_summary(artifact) if artifact else (state.get("draft_md") or "")
    artifact_md = skill.render(artifact) if skill and artifact else None
    combined, citations = resolve_citations(
        answer + (_SPLIT + artifact_md if artifact_md else ""), state.get("evidence", [])
    )
    answer_md, _, artifact_md_resolved = combined.partition(_SPLIT)

    grade = state.get("grade") or {}
    missing = list((state.get("abstain") or {}).get("missing") or [])
    if status == "partial":
        missing = list(grade.get("missing_aspects") or [])
    if artifact:
        missing += list(artifact.get("open_questions") or [])
    remaining: list[Issue] = report.issues if report else []
    cited: list[Citation] = list(citations)

    final = FinalPayload(
        status=status,  # type: ignore[arg-type]
        answer_md=answer_md.strip(),
        citations=cited,
        artifact=artifact,
        artifact_md=artifact_md_resolved.strip() or None if artifact_md else None,
        confidence=None
        if status in {"abstained", "clarification", "out_of_scope"}
        else confidence(
            grade_status=grade.get("status"),
            passed=not (report and report.blocking),
            revision_count=state.get("revision_count", 0),
            abstained=False,
        ),
        missing_info=missing,
        compliance=ComplianceSummary(passed=not (report and report.blocking), warnings=remaining),
    )
    if artifact:
        emit("artifact.ready", {"skill": intent(state), "content": artifact, "rendered_md": final.artifact_md})
    return {"final": final.model_dump(mode="json"), "messages": [AIMessage(final.answer_md)]}
