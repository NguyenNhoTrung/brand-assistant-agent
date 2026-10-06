from typing import Any, Literal, get_args

from pydantic import BaseModel

EventType = Literal[
    "job.started",
    "node.started",
    "node.completed",
    "route.decided",
    "retrieval.sources",
    "token",
    "verification.result",
    "answer.revised",
    "artifact.ready",
    "message.completed",
    "job.failed",
    "job.cancelled",
    "heartbeat",
]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)
TERMINAL_EVENTS: set[str] = {"message.completed", "job.failed", "job.cancelled"}


class EventEnvelope(BaseModel):
    """Field `data` của mỗi entry trong `job:{id}:events` (và của mỗi frame SSE)."""

    v: Literal[1] = 1
    job_id: str
    ts: str
    data: dict[str, Any] | list[Any]
