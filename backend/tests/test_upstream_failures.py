import asyncio
from pathlib import Path
import httpx
import pytest

from app.core.cache import InMemoryTtlCache
from app.services.data_loader import DataLoaderService
from app.services.elexon_client import (
    ElexonClient,
    ElexonPayloadError,
    ElexonUpstreamError,
    ElexonValidationError,
)


def test_upstream_503_raises_explicit_error_without_fixtures() -> None:
    """Never replace an upstream failure with zero generation (P4-05 / ADR-05)."""
    async def run_test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="Elexon Under Maintenance")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            # Use non-existent fixtures dir to test pure live behavior without fallback
            loader = DataLoaderService(
                client=client,
                cache=InMemoryTtlCache(),
                fixtures_dir=Path("/nonexistent/fixtures"),
            )

            with pytest.raises(ElexonUpstreamError) as exc_info:
                await loader.get_january_actuals(force_live=True)

            assert exc_info.value.status_code == 503
            assert "Unable to reach Elexon" in str(exc_info.value) or "Upstream Elexon error" in str(exc_info.value)

    asyncio.run(run_test())


def test_upstream_malformed_payload_raises_error() -> None:
    """Non-list response or invalid JSON should raise ElexonPayloadError, not return zeroes."""
    async def run_test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": "not a list"})

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            with pytest.raises(ElexonPayloadError):
                await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")

    asyncio.run(run_test())


def test_distinguish_real_zero_from_missing() -> None:
    """Verifies that an interval with generation=0 is preserved as 0.0, distinct from None."""
    async def run_test() -> None:
        mock_payload = [
            {
                "dataset": "FUELHH",
                "publishTime": "2026-01-01T01:00:00Z",
                "startTime": "2026-01-01T00:30:00Z",
                "settlementDate": "2026-01-01",
                "settlementPeriod": 2,
                "fuelType": "WIND",
                "generation": 0,  # Real zero (calm day)
            }
        ]

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_payload)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            records = await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
            assert len(records) == 1
            assert records[0].generation_mw == 0.0  # Kept as 0.0

    asyncio.run(run_test())
