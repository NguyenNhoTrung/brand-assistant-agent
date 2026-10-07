import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from shared.contracts import ErrorCode, ProblemDetail

log = structlog.get_logger()

_TITLES = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    422: "Validation error",
    500: "Internal error",
    503: "Service unavailable",
}


class Problem(Exception):
    def __init__(self, status: int, code: ErrorCode, detail: str | None = None):
        self.status, self.code, self.detail = status, code, detail


def _response(request: Request, status: int, code: ErrorCode, detail: str | None) -> JSONResponse:
    body = ProblemDetail(
        title=_TITLES.get(status, "Error"),
        status=status,
        code=code,
        detail=detail,
        request_id=getattr(request.state, "request_id", None),
    )
    headers = {"WWW-Authenticate": 'Basic realm="company-brain"'} if status == 401 else None
    return JSONResponse(
        body.model_dump(exclude_none=True),
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
    )


async def problem_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, Problem)
    return _response(request, exc.status, exc.code, exc.detail)


async def validation_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return _response(request, 422, "validation_error", str(exc.errors()[:3]))


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Lỗi không lường trước → vẫn trả problem+json có request_id (không lộ stacktrace)."""
    log.exception("http.unhandled", error=type(exc).__name__)
    return _response(request, 500, "internal_error", None)
