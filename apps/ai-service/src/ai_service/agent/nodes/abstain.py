import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from ai_service.agent.nodes._common import NOSTREAM, sources_block, started
from ai_service.agent.prompts import load_prompt
from ai_service.agent.schemas import AbstainNote
from ai_service.agent.state import AgentState
from ai_service.llm.client import structured

log = structlog.get_logger()

HEADER = "**Mình chưa đủ thông tin trong knowledge base để trả lời chắc chắn.**"
NOTHING_FOUND = "không có tài liệu nào liên quan trực tiếp"
DEFAULT_SUGGESTION = "hỏi team phụ trách, hoặc bổ sung tài liệu tương ứng vào knowledge base"


def render_abstain(note: AbstainNote) -> str:
    found = "; ".join(f"{f.text} " + "".join(f"[{s}]" for s in f.source_ids) for f in note.found) or NOTHING_FOUND
    missing = "; ".join(note.missing) or "thông tin để trả lời câu hỏi này"
    return (
        f"{HEADER}\n\n"
        f"- **Đã tìm thấy:** {found.strip()}\n"
        f"- **Còn thiếu:** {missing}\n"
        f"- **Gợi ý:** {note.suggestion or DEFAULT_SUGGESTION}"
    )


async def abstain(state: AgentState) -> dict:
    """Khối cố định "Đã tìm thấy / Còn thiếu / Gợi ý" (§12) — LLM ngắn điền nội dung, lỗi → template."""
    started("abstain", "Không đủ thông tin — đang tóm tắt những gì đã tìm thấy")
    evidence = state.get("evidence", [])
    grade = state.get("grade") or {}
    relevant = set(grade.get("relevant_sids") or [])
    shown = [e for e in evidence if e["sid"] in relevant] if relevant else []
    try:
        if not shown:
            raise LookupError("không có evidence liên quan")
        msgs = [
            SystemMessage(load_prompt("abstain").render(sources=sources_block(shown))),
            HumanMessage(
                f"Question: {state['question']}\nMissing according to grading: {grade.get('missing_aspects')}"
            ),
        ]
        note = await structured("chat-fast", AbstainNote).ainvoke(msgs, config=NOSTREAM)
        assert isinstance(note, AbstainNote)
    except Exception as e:
        log.info("abstain.template", reason=str(e))
        note = AbstainNote(found=[], missing=list(grade.get("missing_aspects") or []), suggestion=DEFAULT_SUGGESTION)
    return {"outcome": "abstained", "abstain": note.model_dump(), "draft_md": render_abstain(note)}
