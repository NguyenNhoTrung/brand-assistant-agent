"""MỘT nơi định nghĩa mọi key Redis."""

from uuid import UUID

Id = str | UUID

QUEUE = "queue:jobs"
TRACES_RECENT = "traces:recent"
KB_MANIFEST = "kb:manifest"
KB_INGEST_LOCK = "kb:ingest:lock"  # chỉ một job ingest chạy tại một thời điểm

TTL_1H = 3600
TTL_1D = 86_400
TTL_7D = 7 * TTL_1D
TTL_30D = 30 * TTL_1D
EVENTS_MAXLEN = 5000


def job(job_id: Id) -> str:
    return f"job:{job_id}"


def job_events(job_id: Id) -> str:
    return f"job:{job_id}:events"


def job_cancel(job_id: Id) -> str:
    return f"job:{job_id}:cancel"


def job_msg(job_id: Id) -> str:
    return f"job:{job_id}:msg"


def idem(user_id: str, key: str) -> str:
    return f"idem:{user_id}:{key}"


def user_jobs(user_id: str) -> str:
    return f"user:{user_id}:jobs"


def conv(conv_id: Id) -> str:
    return f"conv:{conv_id}"


def user_convs(user_id: str) -> str:
    return f"user:{user_id}:convs"


def conv_msgs(conv_id: Id) -> str:
    return f"conv:{conv_id}:msgs"


def msg(msg_id: Id) -> str:
    return f"msg:{msg_id}"


def trace(job_id: Id) -> str:
    return f"trace:{job_id}"


def emb(model: str, sha256: str) -> str:
    return f"emb:{model}:{sha256}"
