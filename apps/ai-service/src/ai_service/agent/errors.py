"""Lỗi hạ tầng tạm thời → `RetryPolicy` của node `retrieve` thử lại (§8.2). Không import redis (.importlinter):
nhận diện theo module của exception."""

from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse


class TransientInfraError(Exception):
    pass


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, TransientInfraError | ResponseHandlingException | ConnectionError | TimeoutError):
        return True
    if isinstance(exc, UnexpectedResponse):
        return exc.status_code is not None and exc.status_code >= 500
    module = type(exc).__module__
    return module.startswith("redis") and type(exc).__name__ in {"ConnectionError", "TimeoutError", "BusyLoadingError"}
