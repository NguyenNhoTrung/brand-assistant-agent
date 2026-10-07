from typing import ClassVar

from pydantic import BaseModel, Field

from ai_service.agent.schemas import CitedText


class ComplianceNote(BaseModel):
    requested_claim: str = Field(description="Claim người dùng yêu cầu nhưng vi phạm rule (trích nguyên văn)")
    rule_id: str
    explanation: CitedText = Field(description="Vì sao vi phạm — cite nguồn compliance policy")
    compliant_alternatives: list[str] = Field(description="2–3 cách diễn đạt hợp lệ thay thế")


class CreativeBrief(BaseModel):
    title: str
    objective: CitedText
    target_audience: CitedText
    key_insight: CitedText = Field(description="Từ customer research")
    single_minded_proposition: str = Field(description="PUBLISHABLE — một câu, tuân thủ mọi rule")
    reasons_to_believe: list[CitedText] = Field(description="Product facts")
    tone_and_voice: CitedText = Field(description="Từ brand guidelines")
    mandatory_inclusions: list[CitedText] = Field(description="Disclaimer / câu bắt buộc, nguyên văn")
    do_not_say: list[CitedText] = Field(description="INTERNAL — được phép chứa từ cấm để nhắc team")
    hooks_to_test: list[CitedText] = Field(description="PUBLISHABLE — 2–4 hook, dựa trên creative learnings")
    channels_and_formats: list[str]
    success_metrics: list[str]
    open_questions: list[str] = Field(description="Những gì KB không có — nói thẳng, không bịa")
    compliance_notes: list[ComplianceNote] = Field(description="Claim bị từ chối trong yêu cầu; rỗng nếu không có")

    PUBLISHABLE_FIELDS: ClassVar[set[str]] = {
        "single_minded_proposition",
        "hooks_to_test",
        "compliance_notes.compliant_alternatives",
    }
    REQUIRED_PHRASE_FIELD: ClassVar[str] = "mandatory_inclusions"  # câu bắt buộc (CMP-005…) phải nằm ở đây
    CITED_FIELDS: ClassVar[tuple[str, ...]] = (
        "objective",
        "target_audience",
        "key_insight",
        "reasons_to_believe",
        "tone_and_voice",
        "mandatory_inclusions",
        "hooks_to_test",
    )


SCHEMA = CreativeBrief
