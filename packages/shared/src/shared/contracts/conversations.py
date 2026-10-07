"""Read API của gateway: conversation, message, feedback, nguồn (hover citation), admin KB."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shared.contracts.jobs import AnswerStatus, Citation, ComplianceSummary


class ConversationView(BaseModel):
    id: UUID
    title: str
    updated_at: int
    active_job_id: UUID | None = None


class Feedback(BaseModel):
    rating: Literal[1, -1]  # 👍 / 👎
    comment: str | None = Field(default=None, max_length=2000)


class StepDetail(BaseModel):
    """Một dòng output của bước agent — `value` là chuỗi hoặc danh sách; `md=True` → render Markdown."""

    label: str
    value: str | list[str]
    md: bool = False


class StepView(BaseModel):
    """Một bước agent đã chạy (`node.completed`) — lưu cùng message assistant."""

    node: str
    label: str = ""
    duration_ms: int | None = None
    detail: list[StepDetail] = []


class MessageView(BaseModel):
    """`msg:{id}` — message user hoặc assistant (assistant mang thêm kết quả FinalPayload)."""

    id: UUID
    role: Literal["user", "assistant"]
    content_md: str
    job_id: UUID
    created_at: int | None = None
    status: AnswerStatus | None = None
    citations: list[Citation] = []
    confidence: Literal["high", "medium", "low"] | None = None
    missing_info: list[str] = []
    artifact: dict | None = None
    artifact_md: str | None = None
    compliance: ComplianceSummary | None = None
    feedback: Feedback | None = None
    steps: list[StepView] = []


class SourceView(BaseModel):
    chunk_id: str
    source_path: str
    title: str
    doc_type: str
    section: str = ""
    content: str
    effective_date: str
    version: int = 1
    status: str = "active"  # active | superseded


class KbEntry(BaseModel):
    source_path: str
    title: str
    doc_type: str
    status: str
    version: int
    effective_date: str
    chunk_count: int
    ingested_at: str
    content_hash: str


class IngestRequest(BaseModel):
    recreate: bool = False
