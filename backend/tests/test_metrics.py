import math
from pathlib import Path
import pytest

from app.services.analytics import (
    AnalyticsEngine,
    ForecastMetrics,
    compute_bias,
    compute_mae,
    compute_rmse,
    compute_wape,
)
from app.services.elexon_client import ElexonClient
from app.services.models import AlignedInterval

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


# ---------------------------------------------------------------------------
# P5-02 Tests: MAE & RMSE
# ---------------------------------------------------------------------------


def test_mae_known_values() -> None:
    """MAE calculates exact mean of absolute forecast errors on known pairs (P5-02)."""
    # Errors: |100-80|=20, |90-110|=20, |120-100|=20, |70-110|=40
    # Mean = (20 + 20 + 20 + 40) / 4 = 100 / 4 = 25.0
    pairs = [(100.0, 80.0), (90.0, 110.0), (120.0, 100.0), (70.0, 110.0)]
    mae = compute_mae(pairs)
    assert mae == 25.0

    # Single pair: |5000 - 4500| = 500.0
    assert compute_mae([(5000.0, 4500.0)]) == 500.0

    # Exact match: |1000 - 1000| = 0.0
    assert compute_mae([(1000.0, 1000.0)]) == 0.0


def test_rmse_known_values() -> None:
    """RMSE penalizes large errors and computes square root of mean squared errors (P5-02)."""
    # Squared errors: 20^2=400, 20^2=400, 20^2=400, 40^2=1600
    # Mean squared error = 2800 / 4 = 700.0
    # sqrt(700.0) ≈ 26.46
    pairs = [(100.0, 80.0), (90.0, 110.0), (120.0, 100.0), (70.0, 110.0)]
    rmse = compute_rmse(pairs)
    assert rmse is not None
    assert math.isclose(rmse, 26.46, abs_tol=0.01)

    # Prove RMSE >= MAE (Cauchy-Schwarz inequality)
    assert rmse >= compute_mae(pairs)


def test_mae_and_rmse_empty_pairs_returns_none() -> None:
    """Empty input returns None, never substituting fake zero values (ADR-05)."""
    assert compute_mae([]) is None
    assert compute_rmse([]) is None


# ---------------------------------------------------------------------------
# P5-03 Tests: Signed Bias & WAPE
# ---------------------------------------------------------------------------


def test_signed_bias_overforecast() -> None:
    """Overforecast (F > A) yields positive bias according to UK utility sign convention (P5-03)."""
    # Overforecasting: errors = +50, +30, +40 -> Mean = +40.0
    over_pairs = [(150.0, 100.0), (130.0, 100.0), (140.0, 100.0)]
    bias = compute_bias(over_pairs)
    assert bias == 40.0


def test_signed_bias_underforecast() -> None:
    """Underforecast (F < A) yields negative bias (P5-03)."""
    # Underforecasting: errors = -20, -40, -60 -> Mean = -40.0
    under_pairs = [(80.0, 100.0), (60.0, 100.0), (40.0, 100.0)]
    bias = compute_bias(under_pairs)
    assert bias == -40.0


def test_signed_bias_symmetric_errors_cancel() -> None:
    """Symmetric over/under errors cancel out to 0.0 bias while MAE remains positive."""
    # Pairs with +50 and -50 error
    pairs = [(150.0, 100.0), (50.0, 100.0)]
    assert compute_bias(pairs) == 0.0
    assert compute_mae(pairs) == 50.0  # MAE still detects variation


def test_wape_known_values() -> None:
    """WAPE calculates sum absolute error / sum actual * 100% (P5-03)."""
    # Sum abs errors: 20 + 20 + 20 + 40 = 100
    # Sum actual: 80 + 110 + 100 + 110 = 400
    # WAPE = (100 / 400) * 100% = 25.0%
    pairs = [(100.0, 80.0), (90.0, 110.0), (120.0, 100.0), (70.0, 110.0)]
    wape = compute_wape(pairs)
    assert wape == 25.0


def test_wape_zero_denominator_guardrail() -> None:
    """When total actual generation is zero, WAPE returns None without ZeroDivisionError (ADR-05)."""
    # True calm: actual generation is 0 MW
    calm_pairs = [(50.0, 0.0), (30.0, 0.0)]
    wape = compute_wape(calm_pairs)
    assert wape is None

    # Empty pairs
    assert compute_wape([]) is None


# ---------------------------------------------------------------------------
# Integrated AnalyticsEngine.compute_metrics Tests
# ---------------------------------------------------------------------------


def test_compute_metrics_sample_count_excludes_missing() -> None:
    """Sample count N strictly reflects valid matched intervals, ignoring missing records."""
    from datetime import datetime, timezone

    dt = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # 2 valid matched intervals
    m1 = AlignedInterval(
        interval_id="2026-01-01-01",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=1,
        actual_mw=100.0,
        forecast_mw=120.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    m2 = AlignedInterval(
        interval_id="2026-01-01-02",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=2,
        actual_mw=100.0,
        forecast_mw=80.0,
        cutoff_time_applied=dt,
        status="matched",
    )
    # 1 missing actual
    m3 = AlignedInterval(
        interval_id="2026-01-01-03",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=3,
        actual_mw=None,
        forecast_mw=100.0,
        cutoff_time_applied=dt,
        status="missing_actual",
    )
    # 1 missing forecast
    m4 = AlignedInterval(
        interval_id="2026-01-01-04",
        start_time=dt,
        settlement_date="2026-01-01",
        settlement_period=4,
        actual_mw=100.0,
        forecast_mw=None,
        cutoff_time_applied=dt,
        status="missing_forecast",
    )

    metrics = AnalyticsEngine.compute_metrics([m1, m2, m3, m4])
    # Sample count must be 2, NOT 4!
    assert metrics.sample_count == 2
    assert metrics.mae == 20.0
    assert metrics.rmse == 20.0
    assert metrics.bias == 0.0
    assert metrics.wape == 20.0
    assert metrics.sign_convention == "positive_overforecast"


def test_full_january_metrics_benchmark() -> None:
    """Verifies full statistical benchmark calculation across January 2026 fixtures."""
    client = ElexonClient()
    actuals = client.load_fixture_fuelhh(FIXTURES_DIR / "fuelhh_jan2026_wind.json")
    forecasts = client.load_fixture_windfor(FIXTURES_DIR / "windfor_jan2026.json")

    intervals = AnalyticsEngine.align_intervals(actuals, forecasts, "2026-01", "12:00")
    metrics = AnalyticsEngine.compute_metrics(intervals)

    # 100% matched intervals
    assert metrics.sample_count == 1488

    # Verified benchmark numbers
    assert math.isclose(metrics.mae, 2020.64, abs_tol=0.1)
    assert math.isclose(metrics.rmse, 2481.38, abs_tol=0.1)
    assert math.isclose(metrics.bias, 1806.23, abs_tol=0.1)  # Substantial overforecast
    assert math.isclose(metrics.wape, 17.45, abs_tol=0.1)
    assert metrics.total_actual_mw == 17232137.0
