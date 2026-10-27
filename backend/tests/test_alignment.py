from datetime import date, datetime, timezone
from pathlib import Path
import pytest

from app.services.analytics import (
    AnalyticsEngine,
    compute_day_ahead_cutoff_utc,
    select_operational_forecast,
)
from app.services.elexon_client import ElexonClient
from app.services.models import ForecastRecord, FuelRecord

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_compute_day_ahead_cutoff_utc() -> None:
    """Cutoff on day D-1 is accurately computed in UTC from local UK time."""
    # Delivery on Jan 1 -> Cutoff is Dec 31 at 12:00 UTC
    cutoff_1 = compute_day_ahead_cutoff_utc("2026-01-01", cutoff_time_str="12:00")
    assert cutoff_1 == datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

    # Delivery on Jan 15 -> Cutoff is Jan 14 at 12:00 UTC
    cutoff_15 = compute_day_ahead_cutoff_utc(date(2026, 1, 15), cutoff_time_str="12:00")
    assert cutoff_15 == datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Custom cutoff: 09:30
    cutoff_custom = compute_day_ahead_cutoff_utc("2026-01-20", cutoff_time_str="09:30")
    assert cutoff_custom == datetime(2026, 1, 19, 9, 30, 0, tzinfo=timezone.utc)

    # Malformed cutoff string raises ValueError
    with pytest.raises(ValueError):
        compute_day_ahead_cutoff_utc("2026-01-01", cutoff_time_str="invalid")


def test_reject_late_forecasts_strictly() -> None:
    """Forecasts published strictly after cutoff timestamp MUST be rejected (ADR-04)."""
    cutoff = datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
    target_start = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)

    # Candidate 1: Published D-1 at 07:30 UTC (eligible)
    fc_1 = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 7, 30, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=8500.0,
    )
    # Candidate 2: Published D-1 at 11:30 UTC (eligible, latest before cutoff)
    fc_2 = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 11, 30, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=9200.0,
    )
    # Candidate 3: Published D-1 at 12:00 UTC (exact boundary, eligible)
    fc_boundary = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=9500.0,
    )
    # Candidate 4: Published D-1 at 12:01 UTC (LATE, MUST BE REJECTED)
    fc_late_1 = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 12, 1, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=11000.0,
    )
    # Candidate 5: Published D-1 at 15:30 UTC (LATE, MUST BE REJECTED)
    fc_late_2 = ForecastRecord(
        publish_time=datetime(2026, 1, 14, 15, 30, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=12000.0,
    )
    # Candidate 6: Published on delivery day D at 06:00 UTC (INTRADAY LEAKAGE, REJECTED)
    fc_late_3 = ForecastRecord(
        publish_time=datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc),
        start_time=target_start,
        generation_mw=13000.0,
    )

    all_candidates = [fc_1, fc_2, fc_boundary, fc_late_1, fc_late_2, fc_late_3]

    chosen = select_operational_forecast(all_candidates, cutoff)
    assert chosen is not None
    # Must pick fc_boundary (12:00) as the latest eligible edition
    assert chosen.publish_time == fc_boundary.publish_time
    assert chosen.generation_mw == 9500.0

    # If fc_boundary is removed, must pick fc_2 (11:30)
    candidates_without_boundary = [fc_1, fc_2, fc_late_1, fc_late_2, fc_late_3]
    chosen_2 = select_operational_forecast(candidates_without_boundary, cutoff)
    assert chosen_2 is not None
    assert chosen_2.publish_time == fc_2.publish_time
    assert chosen_2.generation_mw == 9200.0


def test_no_eligible_forecast_returns_none() -> None:
    """When all candidate forecasts are published after cutoff, return None."""
    cutoff = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    target_start = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    late_forecasts = [
        ForecastRecord(
            publish_time=datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc),
            start_time=target_start,
            generation_mw=8000.0,
        ),
        ForecastRecord(
            publish_time=datetime(2026, 1, 1, 18, 30, tzinfo=timezone.utc),
            start_time=target_start,
            generation_mw=8500.0,
        ),
    ]
    chosen = select_operational_forecast(late_forecasts, cutoff)
    assert chosen is None


def test_hourly_forecast_aligns_to_both_half_hours() -> None:
    """Hourly forecast applies to Period 2k-1 and Period 2k (power rate equivalence)."""
    target_date = "2026-01-05"
    cutoff_time = "12:00"

    # Actuals for SP 1 (00:00-00:30) and SP 2 (00:30-01:00)
    actual_sp1 = FuelRecord(
        publish_time=datetime(2026, 1, 5, 0, 45, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc),
        settlement_date=target_date,
        settlement_period=1,
        fuel_type="WIND",
        generation_mw=10000.0,
    )
    actual_sp2 = FuelRecord(
        publish_time=datetime(2026, 1, 5, 1, 15, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 5, 0, 30, tzinfo=timezone.utc),
        settlement_date=target_date,
        settlement_period=2,
        fuel_type="WIND",
        generation_mw=10500.0,
    )

    # 1-hour forecast for hour 00:00:00 (published D-1 at 11:30)
    forecast_h0 = ForecastRecord(
        publish_time=datetime(2026, 1, 4, 11, 30, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc),
        generation_mw=11000.0,
    )

    intervals = AnalyticsEngine.align_intervals(
        actuals=[actual_sp1, actual_sp2],
        forecasts=[forecast_h0],
        target_month="2026-01",
        cutoff_time=cutoff_time,
    )

    # Find SP 1 and SP 2 for 2026-01-05
    int_sp1 = next(i for i in intervals if i.interval_id == "2026-01-05-01")
    int_sp2 = next(i for i in intervals if i.interval_id == "2026-01-05-02")

    # Both SP 1 and SP 2 must inherit the hour 0 forecast (11000 MW)
    assert int_sp1.forecast_mw == 11000.0
    assert int_sp2.forecast_mw == 11000.0
    assert int_sp1.forecast_publish_time == datetime(2026, 1, 4, 11, 30, tzinfo=timezone.utc)
    assert int_sp2.forecast_publish_time == datetime(2026, 1, 4, 11, 30, tzinfo=timezone.utc)

    # SP 1 actual = 10000 -> error = 11000 - 10000 = +1000 MW, shortfall = 1000 * 0.5 = 500 MWh
    assert int_sp1.actual_mw == 10000.0
    assert int_sp1.error_mw == 1000.0
    assert int_sp1.shortfall_mwh == 500.0
    assert int_sp1.status == "matched"

    # SP 2 actual = 10500 -> error = 11000 - 10500 = +500 MW, shortfall = 500 * 0.5 = 250 MWh
    assert int_sp2.actual_mw == 10500.0
    assert int_sp2.error_mw == 500.0
    assert int_sp2.shortfall_mwh == 250.0
    assert int_sp2.status == "matched"


def test_underforecast_has_zero_shortfall() -> None:
    """When forecast < actual (underforecast), error is negative and shortfall is 0 MWh."""
    actual = FuelRecord(
        publish_time=datetime(2026, 1, 10, 1, 0, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc),
        settlement_date="2026-01-10",
        settlement_period=1,
        fuel_type="WIND",
        generation_mw=12000.0,
    )
    forecast = ForecastRecord(
        publish_time=datetime(2026, 1, 9, 11, 30, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc),
        generation_mw=9000.0,
    )

    intervals = AnalyticsEngine.align_intervals(
        actuals=[actual],
        forecasts=[forecast],
        target_month="2026-01",
        cutoff_time="12:00",
    )
    interval = next(i for i in intervals if i.interval_id == "2026-01-10-01")
    assert interval.error_mw == -3000.0  # 9000 - 12000
    assert interval.shortfall_mwh == 0.0  # No procurement shortfall
    assert interval.status == "matched"


def test_missing_data_status_classification() -> None:
    """Unmatched intervals correctly identify missing actual vs missing forecast."""
    # Only actual present for SP 1
    actual = FuelRecord(
        publish_time=datetime(2026, 1, 1, 0, 45, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        settlement_date="2026-01-01",
        settlement_period=1,
        fuel_type="WIND",
        generation_mw=8000.0,
    )
    # Only forecast present for SP 3 (hour 01:00)
    forecast = ForecastRecord(
        publish_time=datetime(2025, 12, 31, 11, 30, tzinfo=timezone.utc),
        start_time=datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc),
        generation_mw=9000.0,
    )

    intervals = AnalyticsEngine.align_intervals(
        actuals=[actual],
        forecasts=[forecast],
        target_month="2026-01",
        cutoff_time="12:00",
    )

    sp1 = next(i for i in intervals if i.interval_id == "2026-01-01-01")
    assert sp1.status == "missing_forecast"
    assert sp1.actual_mw == 8000.0
    assert sp1.forecast_mw is None
    assert sp1.error_mw is None

    sp3 = next(i for i in intervals if i.interval_id == "2026-01-01-03")
    assert sp3.status == "missing_actual"
    assert sp3.actual_mw is None
    assert sp3.forecast_mw == 9000.0
    assert sp3.error_mw is None

    # Unpopulated period (SP 20)
    sp20 = next(i for i in intervals if i.interval_id == "2026-01-01-20")
    assert sp20.status == "missing_both"
    assert sp20.actual_mw is None
    assert sp20.forecast_mw is None


def test_full_month_real_fixture_alignment() -> None:
    """Verifies complete 1,488 half-hour alignment across January 2026 using real fixtures."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json", fuel_type="WIND")
    forecasts = client.load_fixture_windfor(FIXTURES_DIR / "windfor_jan2026.json")

    assert len(actuals) == 1488
    assert len(forecasts) == 18080

    intervals = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month="2026-01",
        cutoff_time="12:00",
    )

    # Must contain exactly 31 * 48 = 1,488 intervals
    assert len(intervals) == 1488

    # 100% of intervals must be matched at 12:00 cutoff
    matched = [i for i in intervals if i.status == "matched"]
    assert len(matched) == 1488

    # Zero look-ahead bias: for every interval, forecast_publish_time <= cutoff_time_applied
    for i in intervals:
        assert i.forecast_publish_time is not None
        assert i.forecast_publish_time <= i.cutoff_time_applied

    # All interval IDs conform to YYYY-MM-DD-SP
    assert intervals[0].interval_id == "2026-01-01-01"
    assert intervals[-1].interval_id == "2026-01-31-48"
