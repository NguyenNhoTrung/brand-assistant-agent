"""Request ID + log truy cập. ASGI thuần (không BaseHTTPMiddleware) → không buffer SSE, contextvars do
dependency bind (`user_id`, `job_id`) vẫn thấy được ở đây khi request kết thúc."""

import re
import time

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from shared.ids import uuid7

log = structlog.get_logger()

HEADER = "x-request-id"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")  # nhận request id từ client/proxy nếu hợp lệ


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(HEADER.encode(), b"").decode()
        request_id = incoming if _VALID.match(incoming) else f"req_{uuid7().hex}"
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(service="gateway", request_id=request_id)
        t0, status = time.monotonic(), 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((HEADER.encode(), request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            if scope["path"] not in {"/healthz", "/readyz"}:
                log.info(
                    "http.request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status,
                    duration_ms=round((time.monotonic() - t0) * 1000),
                )
            structlog.contextvars.clear_contextvars()
