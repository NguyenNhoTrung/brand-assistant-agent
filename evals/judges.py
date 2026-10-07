"""LLM-as-judge cho các metric không chấm được bằng khớp chuỗi (§19.3). Dùng `chat-default` qua `ai_service.llm`."""

from pydantic import BaseModel, Field

from ai_service.llm.client import structured
from ai_service.llm.config import ModelAlias

JUDGE_ALIAS: ModelAlias = "chat-default"


class FactVerdict(BaseModel):
    present: bool = Field(description="True nếu câu trả lời nêu (cùng nghĩa) fact này")
    reason: str


class ClaimVerdict(BaseModel):
    asserted: bool = Field(description="True nếu câu trả lời KHẲNG ĐỊNH claim là đúng (không tính phủ định/cảnh báo)")
    reason: str


class CriterionScore(BaseModel):
    id: str
    score: int = Field(description="1–5")
    reason: str


class RubricVerdict(BaseModel):
    scores: list[CriterionScore]


async def fact_present(answer: str, fact: str) -> FactVerdict:
    """Fallback khi khớp chuỗi trượt — vd. "2-5 days" vs "2–5 business days", "$42.00" vs "$42"."""
    prompt = (
        "You grade a RAG answer. Decide whether the ANSWER states the FACT (same meaning; wording, "
        "number formatting and language may differ).\n\n"
        f"FACT: {fact}\n\nANSWER:\n{answer}"
    )
    return await structured(JUDGE_ALIAS, FactVerdict).ainvoke(prompt)


async def claim_asserted(answer: str, claim: str) -> ClaimVerdict:
    """forbidden_facts: "not FDA approved" nhắc tới chuỗi nhưng không khẳng định → không vi phạm."""
    prompt = (
        "You grade a RAG answer. Decide whether the ANSWER asserts the CLAIM as true. Mentioning it in order "
        "to deny it, warn against it, or say it is unsupported does NOT count.\n\n"
        f"CLAIM: {claim}\n\nANSWER:\n{answer}"
    )
    return await structured(JUDGE_ALIAS, ClaimVerdict).ainvoke(prompt)


async def rubric_scores(rubric: dict, request: str, artifact_md: str, sources: str) -> RubricVerdict:
    """`rubric` = nội dung `rubric.yaml` của skill (criteria + pass_threshold)."""
    criteria = "\n".join(f"- {c['id']}: {c['description']}" for c in rubric["criteria"])
    prompt = (
        "You grade a marketing artifact produced by a RAG assistant. Score each criterion 1–5 "
        "(5 = fully meets it). Return one score per criterion id, in the given order.\n\n"
        f"CRITERIA:\n{criteria}\n\nREQUEST: {request}\n\nSOURCES the assistant had:\n{sources}\n\n"
        f"ARTIFACT:\n{artifact_md}"
    )
    return await structured(JUDGE_ALIAS, RubricVerdict).ainvoke(prompt)
