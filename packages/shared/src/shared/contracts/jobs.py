from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Mode = Literal["auto", "qa", "creative_brief", "insight_summary", "campaign_recommendation", "compliance_review"]
JobType = Literal["chat", "ingest"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
TERMINAL_STATUSES: set[str] = {"succeeded", "failed", "cancelled"}


class JobInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    mode: Mode = "auto"


class JobCreate(BaseModel):
    conversation_id: UUID | None = None
    input: JobInput


class JobCreated(BaseModel):
    job_id: UUID
    conversation_id: UUID
    status: JobStatus
    events_url: str


class JobView(BaseModel):
    job_id: UUID
    conversation_id: UUID
    user_id: str
    type: JobType
    status: JobStatus
    input: JobInput
    error: dict | None = None
    created_at: int
    started_at: int | None = None
    finished_at: int | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


class Citation(BaseModel):
    n: int
    sid: str
    chunk_id: str
    title: str
    section: str = ""
    snippet: str = ""


class FinalPayload(BaseModel):
    """Kết quả chính thức của một lượt — `message.completed` mang payload này."""

    status: Literal["answered", "partial", "abstained", "needs_review", "clarification", "out_of_scope"]
    answer_md: str
    citations: list[Citation] = []
    artifact: dict | None = None
    artifact_md: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    missing_info: list[str] = []
