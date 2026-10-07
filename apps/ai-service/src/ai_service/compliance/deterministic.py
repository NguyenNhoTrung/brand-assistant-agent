"""Lớp 2: regex + `required_phrase` + trần giảm giá — chạy theo FIELD publishable, không theo toàn văn (§11.2).

`do_not_say` của brief chứa chính từ bị cấm, Q&A có thể trích lại câu vi phạm để giải thích → chỉ kiểm tra phần
sẽ được đăng (field publishable) hoặc phần văn bản Q&A đã bỏ trích dẫn/blockquote/code.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

from ai_service.compliance.rules import CheckContext, Rule, load_rules
from shared.contracts import ComplianceIssue as Issue

_FENCED = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|‘[^’\n]*’")
_BLOCKQUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)
_DISCOUNT = re.compile(r"\b(\d{1,3})\s*%\s*(?:off|discount)\b|\b(?:save|giảm)\s*(\d{1,3})\s*%", re.IGNORECASE)


def strip_quoted(md: str) -> str:
    """Q&A: bỏ blockquote, code, đoạn trong ngoặc kép — đó là trích dẫn để giải thích, không phải claim."""
    for pat in (_FENCED, _INLINE_CODE, _BLOCKQUOTE, _QUOTED):
        md = pat.sub(" ", md)
    return md


def _texts(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        if isinstance(value.get("text"), str):  # CitedText
            yield value["text"]
        else:
            for v in value.values():
                yield from _texts(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _texts(v)


def field_texts(obj: Mapping[str, Any], fields: Iterable[str]) -> dict[str, str]:
    """`{"hooks_to_test", "compliance_notes.compliant_alternatives"}` → `{field: văn bản nối}`; hỗ trợ list lồng."""
    out: dict[str, str] = {}
    for path in fields:
        values: list[Any] = [obj]
        for part in path.split("."):
            nxt: list[Any] = []
            for v in values:
                items = v if isinstance(v, list) else [v]
                nxt += [i.get(part) for i in items if isinstance(i, Mapping) and i.get(part) is not None]
            values = nxt
        out[path] = "\n".join(t for v in values for t in _texts(v))
    return out


def check(
    text_by_field: Mapping[str, str],
    rules: Iterable[Rule] | None = None,
    ctx: CheckContext | None = None,
    *,
    required_text: str | None = None,
) -> list[Issue]:
    """`required_text` = văn bản phải chứa `required_phrase` (vd. `mandatory_inclusions`); None → bỏ qua."""
    rules = tuple(rules if rules is not None else load_rules())
    ctx = ctx or CheckContext()
    issues: list[Issue] = []
    for name, text in text_by_field.items():
        for r in rules:
            if not r.applies(ctx):
                continue
            if r.requires_evidence and ctx.clinical_evidence:
                continue  # có study trong product sheet → claim lâm sàng được phép (vẫn phải khớp kết quả)
            for pat in r.compiled_patterns:
                if m := pat.search(text):
                    issues.append(
                        Issue(
                            kind="compliance",
                            rule_id=r.id,
                            severity=r.severity,
                            excerpt=m.group(0),
                            fix_hint=f"[{name}] " + (r.compliant_alternative or r.title),
                        )
                    )
            if r.max_discount_pct is not None:
                for m in _DISCOUNT.finditer(text):
                    pct = int(m.group(1) or m.group(2))
                    if pct > r.max_discount_pct:
                        issues.append(
                            Issue(
                                kind="compliance",
                                rule_id=r.id,
                                severity=r.severity,
                                excerpt=m.group(0),
                                fix_hint=f"[{name}] Max {r.max_discount_pct}% off without CMO approval",
                            )
                        )
    if required_text is not None:
        for r in rules:
            if r.required_phrase and r.applies(ctx) and r.required_phrase.lower() not in required_text.lower():
                issues.append(
                    Issue(
                        kind="compliance",
                        rule_id=r.id,
                        severity=r.severity,
                        excerpt=r.title,
                        fix_hint=f'Add verbatim: "{r.required_phrase}"',
                    )
                )
    return issues
