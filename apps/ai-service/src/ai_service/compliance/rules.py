"""Rules compliance là DỮ LIỆU: `data/compliance/rules.yaml` → `Rule` đã compile regex, cache theo đường dẫn (§11.1)."""

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

import yaml

RULES_FILE = "data/compliance/rules.yaml"


@dataclass(frozen=True)
class CheckContext:
    """Bối cảnh để quyết định rule có áp dụng không (sản phẩm nào, loại nội dung nào, có study không)."""

    products: frozenset[str] = frozenset()
    content_types: frozenset[str] = frozenset()  # testimonial, before_after…
    clinical_evidence: bool = False  # sản phẩm trong bối cảnh có `clinical_studies` → CMP-002 không chặn


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: Literal["block", "warn"]
    description: str = ""
    patterns: tuple[str, ...] = ()
    compliant_alternative: str | None = None
    required_phrase: str | None = None
    requires_evidence: str | None = None
    applies_to: tuple[str, ...] = ()
    applies_to_products: tuple[str, ...] = ()
    max_discount_pct: int | None = None
    compiled_patterns: tuple[re.Pattern[str], ...] = field(default=(), compare=False, repr=False)

    def applies(self, ctx: CheckContext) -> bool:
        """Rule có điều kiện (`applies_to*`) chỉ áp dụng khi bối cảnh khớp; rule không điều kiện luôn áp dụng."""
        if self.applies_to_products and not set(self.applies_to_products) & ctx.products:
            return False
        if self.applies_to and not set(self.applies_to) & ctx.content_types:
            return False
        return True

    def prompt_line(self) -> str:
        parts = [f"- {self.id} [{self.severity}] {self.title}."]
        if self.description:
            parts.append(self.description)
        if self.required_phrase:
            scope = ", ".join(self.applies_to_products or self.applies_to) or "all content"
            parts.append(f'Required phrase for {scope}: "{self.required_phrase}"')
        if self.compliant_alternative:
            parts.append(f'Compliant alternative: "{self.compliant_alternative}"')
        return " ".join(parts)


def _rule(raw: dict[str, Any]) -> Rule:
    patterns = tuple(raw.get("patterns") or ())
    return Rule(
        id=raw["id"],
        title=raw["title"],
        severity=raw["severity"],
        description=raw.get("description", ""),
        patterns=patterns,
        compliant_alternative=raw.get("compliant_alternative"),
        required_phrase=raw.get("required_phrase"),
        requires_evidence=raw.get("requires_evidence"),
        applies_to=tuple(raw.get("applies_to") or ()),
        applies_to_products=tuple(raw.get("applies_to_products") or ()),
        max_discount_pct=raw.get("max_discount_pct"),
        compiled_patterns=tuple(re.compile(p, re.IGNORECASE) for p in patterns),
    )


@cache
def load_rules(path: str = RULES_FILE) -> tuple[Rule, ...]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return tuple(_rule(r) for r in data["rules"])


def rules_prompt(rules: tuple[Rule, ...] | None = None) -> str:
    """Khối rules nạp vào system prompt MỌI lần (lớp phòng thủ 1)."""
    return "\n".join(r.prompt_line() for r in (rules if rules is not None else load_rules()))
