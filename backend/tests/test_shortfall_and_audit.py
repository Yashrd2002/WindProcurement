from datetime import datetime, timezone
import math
from pathlib import Path
import pytest

from app.services.analytics import (
    AnalyticsEngine,
    compute_potential_shortfall,
)
from app.services.elexon_client import ElexonClient
from app.services.models import AlignedInterval, ForecastRecord, FuelRecord

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# P5-04 Tests: Potential Shortfall Volume
# ---------------------------------------------------------------------------


def test_shortfall_calculation_units_and_duration() -> None:
    """Verifies potential shortfall conversion from MW to MWh using 0.5h duration (P5-04)."""
    dt = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)

    # 1. Overforecast: F = 12,000 MW, A = 10,000 MW -> diff = 2,000 MW -> 2000 * 0.5 = 1,000 MWh
    i1 = AlignedInterval(
        interval_id="2026-01-05-25",
        start_time=dt,
        settlement_date="2026-01-05",
        settlement_period=25,
        actual_mw=10000.0,
        forecast_mw=12000.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    # 2. Underforecast: F = 8,000 MW, A = 10,000 MW -> diff = -2,000 MW -> 0.0 MWh
    i2 = AlignedInterval(
        interval_id="2026-01-05-26",
        start_time=dt,
        settlement_date="2026-01-05",
        settlement_period=26,
        actual_mw=10000.0,
        forecast_mw=8000.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    # 3. Exact match: F = 5,000 MW, A = 5,000 MW -> diff = 0 MW -> 0.0 MWh
    i3 = AlignedInterval(
        interval_id="2026-01-05-27",
        start_time=dt,
        settlement_date="2026-01-05",
        settlement_period=27,
        actual_mw=5000.0,
        forecast_mw=5000.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    # 4. Another overforecast: F = 6,000 MW, A = 4,000 MW -> diff = 2,000 MW -> 1,000 MWh
    i4 = AlignedInterval(
        interval_id="2026-01-05-28",
        start_time=dt,
        settlement_date="2026-01-05",
        settlement_period=28,
        actual_mw=4000.0,
        forecast_mw=6000.0,
        cutoff_time_applied=dt,
        status="matched",
    )

    total_sf, count, max_single = compute_potential_shortfall([i1, i2, i3, i4])

    # Total shortfall: 1,000 + 0 + 0 + 1,000 = 2,000.0 MWh
    assert total_sf == 2000.0
    # Exactly 2 intervals experienced shortfalls
    assert count == 2
    # Peak single interval shortfall is 1,000.0 MWh
    assert max_single == 1000.0


def test_shortfall_not_presented_as_financial_loss() -> None:
    """Verifies that shortfall is strictly volumetric (MWh) and distinguishes 0 calm from missing."""
    dt = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Calm period: 0 MW forecast and 0 MW actual -> 0 MWh shortfall
    calm = AlignedInterval(
        interval_id="2026-01-01-01",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=1,
        actual_mw=0.0,
        forecast_mw=0.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    # Missing actual: must not produce fake shortfall
    missing = AlignedInterval(
        interval_id="2026-01-01-02",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=2,
        actual_mw=None,
        forecast_mw=10000.0,
        cutoff_time_applied=dt,
        status="missing_actual",
    )

    total_sf, count, max_sf = compute_potential_shortfall([calm, missing])
    assert total_sf == 0.0
    assert count == 0
    assert max_sf == 0.0


# ---------------------------------------------------------------------------
# P5-05 Tests: Detect Missing & Duplicate Intervals
# ---------------------------------------------------------------------------


def test_audit_detects_duplicate_actuals() -> None:
    """Audit identifies duplicate settlement periods in raw ingestion (P5-05)."""
    # 2 actual records for the exact same settlement period: 2026-01-02 SP 14
    act1 = FuelRecord(
        publish_time=datetime(2026, 1, 2, 7, 0, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 2, 6, 30, tzinfo=timezone.utc),
        settlement_date="2026-01-02",
        settlement_period=14,
        fuel_type="WIND",
        generation_mw=8000.0,
    )
    act1_duplicate = FuelRecord(
        publish_time=datetime(2026, 1, 2, 7, 15, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 2, 6, 30, tzinfo=timezone.utc),
        settlement_date="2026-01-02",
        settlement_period=14,
        fuel_type="WIND",
        generation_mw=8100.0,
    )

    audit = AnalyticsEngine.audit_coverage(
        actuals=[act1, act1_duplicate],
        forecasts=[],
        target_month="2026-01",
        cutoff_time="12:00",
    )

    assert audit.duplicate_actual_count == 1
    assert "2026-01-02-14" in audit.duplicate_actual_intervals


def test_audit_detects_missing_actual_periods() -> None:
    """Audit flags expected calendar intervals absent from the actual dataset (P5-05)."""
    client = ElexonClient()
    all_actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json")

    # Drop period 2026-01-15-24 (SP 24 on Jan 15)
    subset_actuals = [
        a for a in all_actuals if not (a.settlement_date == "2026-01-15" and a.settlement_period == 24)
    ]
    assert len(subset_actuals) == 1487

    audit = AnalyticsEngine.audit_coverage(
        actuals=subset_actuals,
        forecasts=[],
        target_month="2026-01",
        cutoff_time="12:00",
    )

    assert audit.expected_intervals == 1488
    assert audit.missing_actual_count == 1
    assert "2026-01-15-24" in audit.missing_actual_intervals


def test_audit_detects_missing_forecast_at_early_cutoff() -> None:
    """When cutoff is set before forecasts exist, missing forecast intervals are identified."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_sample_success.json")
    # No forecasts provided
    audit = AnalyticsEngine.audit_coverage(
        actuals=actuals,
        forecasts=[],
        target_month="2026-01",
        cutoff_time="12:00",
    )

    # All 1,488 expected periods lack forecasts
    assert audit.missing_forecast_count == 1488
    assert audit.matched_intervals == 0
    assert audit.completeness_pct == 0.0


def test_audit_full_january_fixtures_zero_anomalies() -> None:
    """Verifies 100% integrity on real January 2026 Elexon data: 0 duplicates, 0 missing."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json")
    forecasts = client.load_fixture_windfor(FIXTURES_DIR / "windfor_jan2026.json")

    audit = AnalyticsEngine.audit_coverage(
        actuals=actuals,
        forecasts=forecasts,
        target_month="2026-01",
        cutoff_time="12:00",
    )

    assert audit.expected_intervals == 1488
    assert audit.actual_intervals_found == 1488
    assert audit.forecast_intervals_found == 1488
    assert audit.matched_intervals == 1488
    assert audit.missing_actual_count == 0
    assert audit.missing_forecast_count == 0
    assert audit.duplicate_actual_count == 0
    assert audit.completeness_pct == 100.0
