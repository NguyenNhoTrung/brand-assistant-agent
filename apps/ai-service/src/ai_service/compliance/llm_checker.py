"""Lớp 3: LLM verifier `chat-fast` — đối chiếu rules + nguồn trong MỘT lời gọi (compliance diễn đạt khác + claim
không có nguồn). Lỗi gọi LLM → trả None để `verify` chỉ dùng kết quả deterministic và gắn cờ (§9.4)."""

import re
from collections.abc import Iterable
from typing import Literal

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ai_service.compliance.rules import Rule
from ai_service.llm.client import structured
from ai_service.llm.config import ModelAlias
from shared.contracts import ComplianceIssue as Issue

log = structlog.get_logger()

# §9.4 ghi chat-fast; thực đo trên golden set, nano báo nhầm approved claim là vi phạm (CMP-002/004) và không
# khớp được fact đã dịch sang tiếng Việt → verify chạy trên chat-default để kết quả ổn định.
VERIFIER_ALIAS: ModelAlias = "chat-default"


class LLMIssue(BaseModel):
    reason: str = Field(description="Lập luận ngắn: rule/nguồn nào, vì sao (viết TRƯỚC khi kết luận)")
    is_violation: bool = Field(description="true chỉ khi chắc chắn là vi phạm/claim sai; góp ý văn phong → false")
    kind: Literal["unsupported_claim", "compliance", "brand_voice"]
    rule_id: str | None = Field(description="Rule ID khi kind=compliance/brand_voice, ngược lại null")
    severity: Literal["block", "warn"]
    excerpt: str = Field(description="Đoạn văn bản vi phạm, trích nguyên văn")
    fix_hint: str


class LLMVerdict(BaseModel):
    issues: list[LLMIssue]


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s).strip().lower()


def ground_issues(issues: list[LLMIssue], content: str, rules: Iterable[Rule]) -> list[Issue]:
    """Lọc ảo giác của verifier: excerpt phải thực sự có trong nội dung; rule_id phải tồn tại và severity lấy từ
    rules.yaml (không tin severity LLM tự gán)."""
    by_id = {r.id: r for r in rules}
    haystack = _norm(content)
    out = []
    for i in issues:
        if not i.is_violation:
            continue  # góp ý văn phong, "this is fine but…"
        excerpt = _norm(i.excerpt)
        if not excerpt or excerpt[:60] not in haystack:
            log.info("verify.llm_issue_dropped", reason="excerpt_not_in_content", excerpt=i.excerpt[:80])
            continue
        if i.kind in {"compliance", "brand_voice"}:
            rule = by_id.get(i.rule_id or "")
            if rule is None:
                log.info("verify.llm_issue_dropped", reason="unknown_rule", rule_id=i.rule_id)
                continue
            out.append(
                Issue(kind=i.kind, rule_id=rule.id, severity=rule.severity, excerpt=i.excerpt, fix_hint=i.fix_hint)
            )
        else:
            out.append(Issue(kind=i.kind, severity="block", excerpt=i.excerpt, fix_hint=i.fix_hint))
    return out


async def llm_check(*, system_prompt: str, content: str, sources: str, rules: Iterable[Rule]) -> list[Issue] | None:
    """`content` = phần cần kiểm (Q&A đã bỏ trích dẫn, hoặc field publishable + claim của artifact)."""
    msgs = [
        SystemMessage(system_prompt),
        HumanMessage(f"<sources>\n{sources}\n</sources>\n\n<content_to_check>\n{content}\n</content_to_check>"),
    ]
    try:
        verdict = await structured(VERIFIER_ALIAS, LLMVerdict).ainvoke(msgs, config={"tags": ["nostream"]})
    except Exception as e:
        log.warning("verify.llm_failed", error=str(e))
        return None
    assert isinstance(verdict, LLMVerdict)
    return ground_issues(verdict.issues, content, rules)
