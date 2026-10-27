import logging
import sys
import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("wind_procurement")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide structured logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    log_format = "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format, date_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    # Remove existing handlers to prevent duplicate lines
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logger.setLevel(numeric_level)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID, logs execution time, and attaches tracing headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Honor incoming X-Request-ID or generate new UUID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.perf_counter()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Attach tracing header to response
            response.headers["X-Request-ID"] = request_id

            # Skip verbose logging for static files and simple health polling
            if not path.startswith("/static") and path != "/health/live":
                logger.info(
                    f"request_id={request_id} method={method} path={path} "
                    f"status={response.status_code} duration={duration_ms:.2f}ms"
                )
            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"request_id={request_id} method={method} path={path} "
                f"status=500 duration={duration_ms:.2f}ms error={exc.__class__.__name__}: {exc}",
                exc_info=True,
            )
            raise
