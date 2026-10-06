from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    job_id: str
    user_id: str
    mode: str
    locale: str = "vi"
