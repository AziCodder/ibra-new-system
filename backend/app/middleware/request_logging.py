"""Log HTTP requests and surface unhandled errors in the main log stream."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in {"/health", "/health/live", "/health/ready"}:
            return await call_next(request)

        start = time.perf_counter()
        client = request.client.host if request.client else "-"
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "%s %s failed",
                request.method,
                request.url.path,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "client": client,
                },
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_fn = logger.warning if response.status_code >= 500 else logger.info
        log_fn(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client": client,
            },
        )
        return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        extra={"method": request.method, "path": request.url.path},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
