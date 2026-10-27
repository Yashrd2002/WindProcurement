import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, Optional, Set, Tuple, Type
import httpx

logger = logging.getLogger("wind_procurement.retry")

TRANSIENT_HTTP_STATUSES: Set[int] = {429, 500, 502, 503, 504}

TRANSIENT_HTTP_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


async def execute_with_retry(
    request_callable: Callable[[], Coroutine[Any, Any, httpx.Response]],
    max_retries: int = 3,
    base_delay_seconds: float = 0.3,
    max_delay_seconds: float = 3.0,
    jitter: bool = True,
    operation_name: str = "HTTP request",
) -> httpx.Response:
    """Execute an async HTTP request callable with bounded exponential backoff.

    - Retries transient upstream network exceptions and 429/5xx status codes.
    - Fails immediately on 4xx client errors (400, 401, 403, 404, 422).
    - Respects Retry-After header on 429 responses if present.
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            response = await request_callable()

            # Permanent client error (4xx except 429): fail immediately
            if 400 <= response.status_code < 500 and response.status_code != 429:
                return response

            # If success (2xx, 3xx), return immediately
            if response.status_code < 400:
                return response

            # Transient HTTP status code (429, 5xx)
            if response.status_code in TRANSIENT_HTTP_STATUSES:
                if attempt == max_retries:
                    logger.warning(
                        f"Exhausted {max_retries} retries for {operation_name} "
                        f"(final status={response.status_code})"
                    )
                    return response

                # Check Retry-After header
                retry_after_str = response.headers.get("Retry-After")
                if retry_after_str and retry_after_str.isdigit():
                    delay = min(float(retry_after_str), max_delay_seconds)
                else:
                    delay = min(max_delay_seconds, base_delay_seconds * (2 ** attempt))
                    if jitter:
                        delay += random.uniform(0, 0.1 * delay)

                logger.warning(
                    f"Transient status {response.status_code} on {operation_name} "
                    f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                continue

            return response

        except TRANSIENT_HTTP_EXCEPTIONS as exc:
            last_exception = exc
            if attempt == max_retries:
                logger.error(
                    f"Exhausted {max_retries} retries for {operation_name} on "
                    f"{exc.__class__.__name__}: {exc}"
                )
                raise

            delay = min(max_delay_seconds, base_delay_seconds * (2 ** attempt))
            if jitter:
                delay += random.uniform(0, 0.1 * delay)

            logger.warning(
                f"Transient exception {exc.__class__.__name__} on {operation_name} "
                f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

        except Exception as exc:
            # Non-transient exception: do not retry
            logger.error(f"Non-transient exception on {operation_name}: {exc}")
            raise

    if last_exception:
        raise last_exception
    raise RuntimeError(f"Unexpected termination of retry loop for {operation_name}")
