from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path
import pytest

from app.services.analytics import (
    AnalyticsEngine,
    build_daily_trends,
    classify_data_quality_status,
    compute_day_ahead_cutoff_utc,
    find_largest_error_intervals,
    select_operational_forecast,
)
from app.services.elexon_client import ElexonClient
from app.services.models import AlignedInterval, ForecastRecord, FuelRecord

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# P5-06 Tests: Data Quality Status Classification
# ---------------------------------------------------------------------------


def test_data_quality_status_thresholds() -> None:
    """Verifies Complete, Partial, Stale, and Degraded quality thresholds (P5-06)."""
    # 1. Complete: 100% completeness, zero duplicates, fresh forecast
    status_1, notes_1 = classify_data_quality_status(100.0, duplicate_count=0, max_forecast_age_hours=12.0)
    assert status_1 == "complete"
    assert "Complete" in notes_1[0]

    # 2. Complete boundary: 98.5%
    status_2, _ = classify_data_quality_status(98.5, duplicate_count=0)
    assert status_2 == "complete"

    # 3. Partial: 85.0% completeness
    status_3, notes_3 = classify_data_quality_status(85.0, duplicate_count=0)
    assert status_3 == "partial"
    assert "85.0%" in notes_3[0]

    # 4. Partial due to duplicates even if 100% matched
    status_dup, notes_dup = classify_data_quality_status(100.0, duplicate_count=3)
    assert status_dup == "partial"
    assert "Duplicate" in notes_dup[0]

    # 5. Stale: forecast age > 48 hours
    status_stale, notes_stale = classify_data_quality_status(100.0, max_forecast_age_hours=52.0)
    assert status_stale == "stale"
    assert "stale" in notes_stale[0]

    # 6. Degraded: 30.0% completeness
    status_deg, notes_deg = classify_data_quality_status(30.0)
    assert status_deg == "degraded"

    # 7. Empty: 0.0% completeness
    status_empty, notes_empty = classify_data_quality_status(0.0)
    assert status_empty == "empty"


# ---------------------------------------------------------------------------
# P5-07 Tests: Summary Aggregation & Reconciliation
# ---------------------------------------------------------------------------


def test_daily_trends_reconciles_to_monthly_aggregates() -> None:
    """Proves that daily aggregated energy volumes reconcile to monthly totals (P5-07)."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json")
    forecasts = client.load_fixture_windfor(FIXTURES_DIR / "windfor_jan2026.json")

    intervals = AnalyticsEngine.align_intervals(actuals, forecasts, "2026-01", "12:00")
    daily_trends = build_daily_trends(intervals)

    # January has 31 days
    assert len(daily_trends) == 31
    assert daily_trends[0].date == "2026-01-01"
    assert daily_trends[-1].date == "2026-01-31"

    # Every day has exactly 48 matched intervals
    for day in daily_trends:
        assert day.matched_intervals == 48
        assert day.expected_intervals == 48
        assert day.actual_generation_mwh > 0.0

    # Reconciliation 1: Total actual generation
    monthly_actual_mwh = sum(i.actual_mw * 0.5 for i in intervals if i.actual_mw is not None)
    sum_daily_actual_mwh = sum(day.actual_generation_mwh for day in daily_trends)
    assert math.isclose(sum_daily_actual_mwh, monthly_actual_mwh, rel_tol=1e-4)

    # Reconciliation 2: Total potential shortfall volume
    monthly_shortfall_mwh = sum(i.shortfall_mwh for i in intervals if i.shortfall_mwh is not None)
    sum_daily_shortfall_mwh = sum(day.shortfall_mwh for day in daily_trends)
    assert math.isclose(sum_daily_shortfall_mwh, monthly_shortfall_mwh, rel_tol=1e-4)


def test_largest_error_intervals_ranking() -> None:
    """Verifies that largest error intervals are ranked strictly descending by absolute deviation (P5-07)."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json")
    forecasts = client.load_fixture_windfor(FIXTURES_DIR / "windfor_jan2026.json")

    intervals = AnalyticsEngine.align_intervals(actuals, forecasts, "2026-01", "12:00")
    largest_5 = find_largest_error_intervals(intervals, limit=5)

    assert len(largest_5) == 5

    # Check strictly descending absolute error
    for idx in range(len(largest_5) - 1):
        assert largest_5[idx].abs_error_mw >= largest_5[idx + 1].abs_error_mw

    # Check fields and direction
    for item in largest_5:
        assert item.abs_error_mw == abs(item.error_mw)
        if item.error_mw > 0:
            assert item.direction == "overforecast"
            assert item.shortfall_mwh > 0.0
        else:
            assert item.direction == "underforecast"
            assert item.shortfall_mwh == 0.0


# ---------------------------------------------------------------------------
# P5-08 Tests: Regression & Edge Cases
# ---------------------------------------------------------------------------


def test_cutoff_strict_second_boundary_regression() -> None:
    """Regression test: exactly at cutoff passes; 1 second after fails (P5-08)."""
    cutoff = datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
    target_start = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)

    # Candidate exactly on the second
    fc_exact = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=9000.0,
    )
    # Candidate 1 second late
    fc_1sec_late = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 12, 0, 1, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=9500.0,
    )

    chosen = select_operational_forecast([fc_exact, fc_1sec_late], cutoff)
    assert chosen is not None
    assert chosen.publish_time == fc_exact.publish_time
    assert chosen.generation_mw == 9000.0


def test_timezone_conversion_bst_vs_gmt() -> None:
    """Verifies that cutoff computation handles timezone offsets correctly (P5-08)."""
    # In January, Europe/London is GMT (UTC+0)
    cutoff_jan = compute_day_ahead_cutoff_utc("2026-01-10", cutoff_time_str="12:00", tz_name="Europe/London")
    assert cutoff_jan == datetime(2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc)

    # In July, Europe/London is BST (UTC+1), so 12:00 local is 11:00 UTC
    cutoff_jul = compute_day_ahead_cutoff_utc("2026-07-10", cutoff_time_str="12:00", tz_name="Europe/London")
    assert cutoff_jul == datetime(2026, 7, 9, 11, 0, 0, tzinfo=timezone.utc)


def test_empty_dataset_regression_no_crash() -> None:
    """Completely empty actuals and forecasts return clean empty structures without crash (P5-08)."""
    intervals = AnalyticsEngine.align_intervals([], [], target_month="2026-01", cutoff_time="12:00")
    assert len(intervals) == 1488
    # All intervals must be missing_both
    assert all(i.status == "missing_both" for i in intervals)

    metrics = AnalyticsEngine.compute_metrics(intervals)
    assert metrics.sample_count == 0
    assert metrics.mae is None
    assert metrics.rmse is None
    assert metrics.bias is None
    assert metrics.wape is None

    trends = build_daily_trends(intervals)
    assert len(trends) == 31
    assert all(t.matched_intervals == 0 for t in trends)

    largest = find_largest_error_intervals(intervals)
    assert len(largest) == 0
