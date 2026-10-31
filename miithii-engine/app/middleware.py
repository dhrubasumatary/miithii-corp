"""Request context middleware: request-ID propagation + structured access logs.

Ticket/doc text must never be logged (see docs/evidence/pii-flow-map.md);
this middleware only ever sees method, path, status, and duration.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

_CONTEXT_KEYS = ("request_id", "method", "path")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed")
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        logger.info(
            "request_completed",
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        structlog.contextvars.unbind_contextvars(*_CONTEXT_KEYS)
        return response
