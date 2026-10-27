"""End-to-End Integration Tests for Wind Procurement Platform (P7-01 & P7-02).

Validates full January 2026 data stream (1,488 settlement intervals),
real Elexon BMRS data semantics, cutoff time adherence, and multi-endpoint consistency.
"""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.analytics import AnalyticsEngine
from app.services.data_loader import DataLoaderService
from app.core.cache import get_cache
from app.core.config import get_settings


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_full_january_data_coverage_and_realism():
    """P7-02: Verify real January 2026 data coverage and verify no invented data."""
    async def _run():
        settings = get_settings()
        cache = get_cache(default_ttl=settings.cache_ttl_seconds)
        loader = DataLoaderService(cache=cache, settings=settings, use_fixtures=True)

        actuals, actuals_report, _ = await loader.get_january_actuals()
        forecasts, forecasts_report, _ = await loader.get_january_forecasts()
        return actuals, forecasts

    actuals, forecasts = asyncio.run(_run())

    # 1. Total count check
    # 31 days * 48 settlement periods = 1,488 periods in January
    assert len(actuals) >= 1488, f"Expected at least 1488 actual records, got {len(actuals)}"
    assert len(forecasts) >= 1488, f"Expected at least 1488 forecast records, got {len(forecasts)}"

    # 2. Check time boundaries: strictly January 2026
    for a in actuals:
        assert a.start_time.year == 2026
        assert a.start_time.month == 1
        assert a.fuel_type == "WIND"
        assert a.generation_mw >= 0.0

    for f in forecasts:
        assert f.start_time.year == 2026
        assert f.start_time.month == 1
        assert f.generation_mw >= 0.0
        assert f.publish_time is not None

    # 3. Test Alignment under 12:00 D-1 Cutoff
    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month="2026-01",
        cutoff_time="12:00",
    )

    assert len(aligned) == 1488, f"Expected 1488 aligned intervals, got {len(aligned)}"

    # Check that 100% of intervals are matched
    matched_count = sum(1 for item in aligned if item.status == "matched")
    assert matched_count == 1488, f"Expected 1488 matched intervals, got {matched_count}"

    # Verify no look-ahead bias: every single forecast publish time <= cutoff time
    for item in aligned:
        assert item.forecast_publish_time is not None
        assert item.forecast_publish_time <= item.cutoff_time_applied, (
            f"Look-ahead bias detected in {item.interval_id}: "
            f"publish_time {item.forecast_publish_time} > cutoff {item.cutoff_time_applied}"
        )


def test_e2e_overview_and_timeseries_consistency(client: TestClient):
    """P7-01: Exercise /overview and /timeseries endpoints end-to-end."""
    # 1. Query Overview
    overview_resp = client.get("/api/v1/overview?month=2026-01&cutoff=12:00")
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()

    assert overview_data["target_month"] == "2026-01"
    assert overview_data["cutoff_time"] == "12:00"
    assert overview_data["completeness_pct"] == 100.0
    assert overview_data["total_expected_intervals"] == 1488
    assert overview_data["total_matched_intervals"] == 1488
    assert overview_data["missing_actual_intervals"] == 0
    assert overview_data["missing_forecast_intervals"] == 0
    assert overview_data["data_status"] == "complete"

    # Known quantitative benchmarks
    assert round(overview_data["mae"], 2) == 2020.64
    assert round(overview_data["rmse"], 2) == 2481.38
    assert round(overview_data["bias"], 2) == 1806.23
    assert round(overview_data["wape"], 2) == 17.45
    assert round(overview_data["potential_shortfall_mwh"], 1) == 1423598.0

    # 2. Query Timeseries
    timeseries_resp = client.get("/api/v1/timeseries?month=2026-01&cutoff=12:00")
    assert timeseries_resp.status_code == 200
    timeseries_data = timeseries_resp.json()

    assert timeseries_data["total_points"] == 1488
    assert timeseries_data["matched_points"] == 1488
    assert len(timeseries_data["points"]) == 1488

    # Reconcile timeseries points sum with overview totals
    total_shortfall_from_points = sum(
        p["shortfall_mwh"] for p in timeseries_data["points"] if p["shortfall_mwh"] is not None
    )
    assert round(total_shortfall_from_points, 1) == round(overview_data["potential_shortfall_mwh"], 1)


def test_e2e_intervals_pagination_and_filtering(client: TestClient):
    """P7-01: Exercise /intervals with pagination, date ranges, and status filters."""
    # 1. Page 1 default (48 records = 1 day)
    resp1 = client.get("/api/v1/intervals?month=2026-01&cutoff=12:00&page=1&page_size=48")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 1488
    assert data1["page"] == 1
    assert data1["page_size"] == 48
    assert data1["total_pages"] == 31
    assert len(data1["items"]) == 48
    assert data1["items"][0]["settlement_date"] == "2026-01-01"
    assert data1["items"][0]["settlement_period"] == 1

    # 2. Last page (Page 31)
    resp31 = client.get("/api/v1/intervals?month=2026-01&cutoff=12:00&page=31&page_size=48")
    assert resp31.status_code == 200
    data31 = resp31.json()
    assert len(data31["items"]) == 48
    assert data31["items"][-1]["settlement_date"] == "2026-01-31"
    assert data31["items"][-1]["settlement_period"] == 48

    # 3. Date range filtering: Week 1 (Jan 1 to Jan 7)
    week1_resp = client.get(
        "/api/v1/intervals?month=2026-01&cutoff=12:00&start_date=2026-01-01&end_date=2026-01-07&page=1&page_size=100"
    )
    assert week1_resp.status_code == 200
    week1_data = week1_resp.json()
    # 7 days * 48 = 336 periods
    assert week1_data["total"] == 336

    # 4. Filter by status: matched
    matched_resp = client.get("/api/v1/intervals?month=2026-01&cutoff=12:00&status_filter=matched")
    assert matched_resp.status_code == 200
    assert matched_resp.json()["total"] == 1488


def test_e2e_quality_audit_report(client: TestClient):
    """P7-01: Verify /quality returns compliant regulatory audit checks."""
    resp = client.get("/api/v1/quality?month=2026-01&cutoff=12:00")
    assert resp.status_code == 200
    quality = resp.json()

    assert quality["overall_status"] == "complete"
    assert quality["completeness_pct"] == 100.0
    assert quality["expected_intervals"] == 1488
    assert quality["matched_intervals"] == 1488
    assert quality["missing_actual_count"] == 0
    assert quality["missing_forecast_count"] == 0

    # Ensure all audit categories passed
    audit_statuses = [a["status"] for a in quality["audits"]]
    assert all(status == "pass" for status in audit_statuses)
