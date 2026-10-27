import asyncio
import time
import httpx
import pytest

from app.core.retry import execute_with_retry


def test_retry_succeeds_after_transient_503() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls < 2:
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(200, json={"status": "recovered"})

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_503_retry",
        )
        assert response.status_code == 200
        assert response.json() == {"status": "recovered"}
        assert calls == 2

    asyncio.run(run_test())


def test_retry_succeeds_after_connect_timeout() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectTimeout("Connection timed out")
            return httpx.Response(200, json={"status": "ok"})

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=2,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_timeout_retry",
        )
        assert response.status_code == 200
        assert calls == 2

    asyncio.run(run_test())


def test_retry_exhausted_returns_final_5xx_status() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(502, text="Bad Gateway")

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=2,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_exhausted_retry",
        )
        assert response.status_code == 502
        assert calls == 3  # Initial + 2 retries

    asyncio.run(run_test())


def test_permanent_400_not_retried() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(400, json={"error": "Bad Request"})

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_400_no_retry",
        )
        assert response.status_code == 400
        assert calls == 1  # Exactly 1 call, zero retries

    asyncio.run(run_test())


def test_permanent_404_not_retried() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(404, text="Not Found")

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_404_no_retry",
        )
        assert response.status_code == 404
        assert calls == 1  # Exactly 1 call, zero retries

    asyncio.run(run_test())


def test_retry_after_header_respected_on_429() -> None:
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def fake_request() -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                # 429 with Retry-After 0 seconds
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"status": "rate_limit_cleared"})

        response = await execute_with_retry(
            request_callable=fake_request,
            max_retries=2,
            base_delay_seconds=0.01,
            max_delay_seconds=0.1,
            jitter=False,
            operation_name="test_429_retry",
        )
        assert response.status_code == 200
        assert calls == 2

    asyncio.run(run_test())
