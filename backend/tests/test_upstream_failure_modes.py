"""Upstream Failure Mode Simulation Tests for Wind Procurement Platform (P7-04).

Simulates upstream Elexon failure states:
- Connection and read timeouts
- HTTP 429 Too Many Requests (Rate limiting)
- HTTP 500 / 502 / 503 / 504 Gateway errors
- HTML error pages / malformed non-JSON responses
- Empty payload responses
- Verifies clean HTTP responses and absence of unhandled server crashes.
"""

import asyncio
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_data_loader
from app.core.cache import InMemoryTtlCache
from app.core.config import Settings
from app.services.data_loader import DataLoaderService
from app.services.elexon_client import (
    ElexonClient,
    ElexonUpstreamError,
)
from app.services.analytics import AnalyticsEngine, classify_data_quality_status


def test_simulate_upstream_connection_timeout():
    """P7-04: Upstream connection timeout raises clean ElexonUpstreamError."""
    async def _test():
        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("Connection timed out to BMRS API")

        test_settings = Settings(retry_max_attempts=1, retry_base_delay_seconds=0.01)
        transport = httpx.MockTransport(timeout_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client, settings=test_settings)
            loader = DataLoaderService(client=client, cache=InMemoryTtlCache(), fixtures_dir=Path("/nonexistent"))

            with pytest.raises(ElexonUpstreamError) as exc_info:
                await loader.get_january_actuals(force_live=True)

            assert exc_info.value.status_code == 503
            assert "Unable to reach Elexon BMRS API" in str(exc_info.value)

    asyncio.run(_test())


def test_simulate_upstream_429_rate_limit():
    """P7-04: HTTP 429 Rate Limit response is caught and reported accurately."""
    async def _test():
        async def rate_limit_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "10"}, text="Rate limit exceeded")

        test_settings = Settings(retry_max_attempts=1, retry_base_delay_seconds=0.01)
        transport = httpx.MockTransport(rate_limit_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client, settings=test_settings)
            loader = DataLoaderService(client=client, cache=InMemoryTtlCache(), fixtures_dir=Path("/nonexistent"))

            with pytest.raises(ElexonUpstreamError) as exc_info:
                await loader.get_january_forecasts(force_live=True)

            assert exc_info.value.status_code == 429
            assert "Rate limit" in str(exc_info.value) or "429" in str(exc_info.value)

    asyncio.run(_test())


def test_simulate_upstream_html_502_bad_gateway():
    """P7-04: Upstream HTML proxy 502 error page raises ElexonUpstreamError, not JSONDecodeError."""
    async def _test():
        html_error = "<html><head><title>502 Bad Gateway</title></head><body><h1>Bad Gateway</h1></body></html>"
        async def gateway_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text=html_error, headers={"Content-Type": "text/html"})

        test_settings = Settings(retry_max_attempts=1, retry_base_delay_seconds=0.01)
        transport = httpx.MockTransport(gateway_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client, settings=test_settings)
            loader = DataLoaderService(client=client, cache=InMemoryTtlCache(), fixtures_dir=Path("/nonexistent"))

            with pytest.raises(ElexonUpstreamError) as exc_info:
                await loader.get_january_actuals(force_live=True)

            assert exc_info.value.status_code == 502

    asyncio.run(_test())


def test_simulate_upstream_empty_dataset_classification():
    """P7-04: Empty dataset from upstream correctly classifies data quality as 'empty'."""
    aligned = AnalyticsEngine.align_intervals(
        actuals=[],
        forecasts=[],
        target_month="2026-01",
        cutoff_time="12:00",
    )
    audit = AnalyticsEngine.audit_coverage(actuals=[], forecasts=[], target_month="2026-01")
    assert audit.matched_intervals == 0
    assert audit.completeness_pct == 0.0
    assert audit.missing_actual_count == 1488
    assert audit.missing_forecast_count == 1488

    status, notes = classify_data_quality_status(audit.completeness_pct, duplicate_count=0)
    assert status == "empty"
    assert "No matched settlement periods" in notes[0]


def test_api_layer_survives_upstream_failure_with_proper_http_status():
    """P7-04: API endpoint returns structured error response when upstream is down."""
    class FailingLoader:
        async def get_january_actuals(self, *args, **kwargs):
            raise ElexonUpstreamError(503, "Elexon BMRS API service unavailable during scheduled maintenance.")

        async def get_january_forecasts(self, *args, **kwargs):
            raise ElexonUpstreamError(503, "Elexon BMRS API service unavailable.")

    app.dependency_overrides[get_data_loader] = lambda: FailingLoader()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v1/overview?month=2026-01&cutoff=12:00")
            assert resp.status_code in [502, 503]
            data = resp.json()
            assert "detail" in data
            assert "Elexon BMRS API service unavailable" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_data_loader, None)
