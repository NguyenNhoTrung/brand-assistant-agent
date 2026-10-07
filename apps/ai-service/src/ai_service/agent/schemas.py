"""Structured output cho mọi bước "quyết định" (§9.6).

Schema gửi cho LLM (`json_schema`, strict) KHÔNG dùng giá trị mặc định / min_length — OpenAI strict yêu cầu mọi
field đều `required`; ràng buộc kiểu "ít nhất 1 nguồn" do `verify` kiểm tra deterministic.
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field

from shared.contracts import Citation, ComplianceIssue, ComplianceSummary, FinalPayload

DocType = Literal["product", "brand_guideline", "compliance", "sop", "customer_research", "creative_learning"]
Intent = Literal[
    "qa", "creative_brief", "insight_summary", "campaign_recommendation", "compliance_review", "out_of_scope"
]
DOC_TYPES: tuple[str, ...] = get_args(DocType)

Issue = ComplianceIssue
ResolvedCitation = Citation

__all__ = [
    "DOC_TYPES",
    "AbstainNote",
    "CitedText",
    "ComplianceSummary",
    "DocType",
    "EvidenceGrade",
    "FinalPayload",
    "Intent",
    "Issue",
    "ResolvedCitation",
    "RetrievalPlan",
    "RetrievalQuery",
    "RouteDecision",
    "VerificationReport",
]


class RouteDecision(BaseModel):
    intent: Intent
    doc_types: list[DocType] = Field(description="Gợi ý filter; rỗng = tất cả")
    product_refs: list[str] = Field(description="Tên sản phẩm được nhắc tới (kể cả qua đại từ trong hội thoại)")
    needs_clarification: bool
    clarification_question: str | None


class RetrievalQuery(BaseModel):
    text: str = Field(description="Câu truy vấn theo ngôn ngữ gốc → nhánh dense")
    text_en: str = Field(description="Bản tiếng Anh, giàu từ khóa → nhánh BM25 (KB tiếng Anh)")
    doc_types: list[DocType] = Field(description="Rỗng = không lọc")


class RetrievalPlan(BaseModel):
    question: str = Field(description="Câu hỏi standalone (đã gộp ngữ cảnh hội thoại), giữ ngôn ngữ người dùng")
    queries: list[RetrievalQuery] = Field(description="1–3 truy vấn")
    product: str | None = Field(description="Tên sản phẩm chính nếu có (cho kế hoạch retrieve của skill)")
    channel: str | None = Field(description="Kênh quảng cáo nếu có (TikTok, Instagram Reels…)")
    category: str | None = Field(description="Ngành hàng/loại sản phẩm, vd. 'skincare serum', 'sunscreen'")


class EvidenceGrade(BaseModel):
    status: Literal["sufficient", "partial", "insufficient"]
    relevant_sids: list[str]
    covered_aspects: list[str]
    missing_aspects: list[str]
    rewrite_query: str | None = Field(description="Chỉ khi insufficient: truy vấn tiếng Anh tốt hơn để tìm lại")


class VerificationReport(BaseModel):
    passed: bool
    issues: list[Issue] = []
    llm_checked: bool = True  # False → LLM verifier lỗi, chỉ có kết quả deterministic

    @property
    def blocking(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "block"]


class CitedText(BaseModel):
    text: str
    source_ids: list[str] = Field(description="sid của <source> hỗ trợ, vd. ['S2']; ít nhất 1")


class AbstainNote(BaseModel):
    found: list[CitedText] = Field(description="Những gì KB CÓ liên quan tới câu hỏi, mỗi ý kèm sid")
    missing: list[str] = Field(description="Thông tin còn thiếu để trả lời")
    suggestion: str = Field(description="Gợi ý: hỏi team nào / bổ sung tài liệu nào")
