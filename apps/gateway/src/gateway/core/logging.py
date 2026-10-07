import logging
import sys

import structlog

from gateway.settings import settings


def configure_logging() -> None:
    """Terminal → dễ đọc; container (không TTY) → JSON một dòng có `request_id`, `user_id`, `job_id` (§21.1)."""
    tail: list[structlog.typing.Processor] = (
        [structlog.dev.ConsoleRenderer()]
        if sys.stderr.isatty()
        else [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer(ensure_ascii=False)]
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            *tail,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level.upper())),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
