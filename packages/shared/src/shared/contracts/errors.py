from typing import Literal

from pydantic import BaseModel

ErrorCode = Literal[
    "auth_required",
    "auth_invalid",
    "forbidden",
    "validation_error",
    "job_not_found",
    "conversation_not_found",
    "message_not_found",
    "source_not_found",
    "job_timeout",
    "llm_unavailable",
    "internal_error",
]


class ProblemDetail(BaseModel):
    """RFC 9457 `application/problem+json`."""

    type: str = "about:blank"
    title: str
    status: int
    code: ErrorCode
    detail: str | None = None
    request_id: str | None = None
