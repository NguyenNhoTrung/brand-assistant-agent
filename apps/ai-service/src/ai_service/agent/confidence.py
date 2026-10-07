"""Confidence deterministic theo bảng §9.6 — không hỏi LLM "bạn chắc bao nhiêu"."""

from typing import Literal

Confidence = Literal["high", "medium", "low"]


def confidence(*, grade_status: str | None, passed: bool, revision_count: int, abstained: bool) -> Confidence | None:
    if abstained:
        return None  # UI hiển thị khối "Không đủ thông tin" thay cho badge
    if not passed:
        return "low"  # vẫn fail sau khi hết lượt revise → needs_review
    if grade_status == "sufficient" and revision_count == 0:
        return "high"
    return "medium"  # partial, hoặc phải revise ≥ 1 lần mới pass
