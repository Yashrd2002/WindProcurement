import asyncio
from pathlib import Path
import httpx
import pytest

from app.core.cache import InMemoryTtlCache
from app.services.data_loader import DataLoaderService
from app.services.elexon_client import ElexonClient

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_offline_deterministic_execution() -> None:
    """Deterministic offline execution: identical results across successive runs."""
    async def run_test() -> None:
        cache = InMemoryTtlCache()
        loader = DataLoaderService(cache=cache, fixtures_dir=FIXTURES_DIR, use_fixtures=True)

        # Run 1: loads from fixture
        actuals_1, report_1, hit_1 = await loader.get_january_actuals(force_live=False)
        assert len(actuals_1) == 1488
        assert hit_1 is False
        assert report_1.valid_count == 1488

        # Run 2: served from in-memory cache
        actuals_2, report_2, hit_2 = await loader.get_january_actuals(force_live=False)
        assert len(actuals_2) == 1488
        assert hit_2 is True

        # Run 3: forecasts load from fixture, then cache
        forecasts_1, f_rep_1, f_hit_1 = await loader.get_january_forecasts(force_live=False)
        assert len(forecasts_1) == 18080
        assert f_hit_1 is False

        forecasts_2, f_rep_2, f_hit_2 = await loader.get_january_forecasts(force_live=False)
        assert len(forecasts_2) == 18080
        assert f_hit_2 is True

        # Strict determinism: start_times match exactly
        assert [r.start_time for r in actuals_1] == [r.start_time for r in actuals_2]
        assert [r.start_time for r in forecasts_1] == [r.start_time for r in forecasts_2]

    asyncio.run(run_test())


def test_empty_upstream_data_handling() -> None:
    """Empty upstream response should be handled cleanly without crash or fake zeroes."""
    async def run_test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            records = await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
            assert len(records) == 0  # Cleanly returns empty list

    asyncio.run(run_test())


def test_timeout_recovery_with_retry() -> None:
    """Verifies that a transient timeout on attempt 1 recovers on attempt 2."""
    calls = 0

    async def run_test() -> None:
        nonlocal calls

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("Read timed out")
            # Attempt 2 succeeds
            return httpx.Response(
                200,
                json=[
                    {
                        "dataset": "FUELHH",
                        "publishTime": "2026-01-01T01:00:00Z",
                        "startTime": "2026-01-01T00:30:00Z",
                        "settlementDate": "2026-01-01",
                        "settlementPeriod": 2,
                        "fuelType": "WIND",
                        "generation": 11000,
                    }
                ],
            )

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            records = await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
            assert len(records) == 1
            assert records[0].generation_mw == 11000.0
            assert calls == 2  # Proves retry occurred

    asyncio.run(run_test())


def test_cache_invalidation_and_expiry() -> None:
    """Verifies cache invalidation triggers a fresh load on subsequent call."""
    async def run_test() -> None:
        cache = InMemoryTtlCache(default_ttl_seconds=3600)
        loader = DataLoaderService(cache=cache, fixtures_dir=FIXTURES_DIR, use_fixtures=True)

        # Call 1: miss
        _, _, hit1 = await loader.get_january_actuals(force_live=False)
        assert hit1 is False

        # Call 2: hit
        _, _, hit2 = await loader.get_january_actuals(force_live=False)
        assert hit2 is True

        # Invalidate
        cache.invalidate("actuals:2026-01:WIND")

        # Call 3: fresh load after invalidation
        _, _, hit3 = await loader.get_january_actuals(force_live=False)
        assert hit3 is False

    asyncio.run(run_test())
