"""Metric Reconciliation Test Suite for Wind Procurement Platform (P7-03).

Performs independent, manual mathematical computations of MAE, RMSE, Signed Bias,
WAPE, and Potential Shortfall Volume (MWh) without using the analytics engine,
then reconciles the independent manual results against the API output.
"""

import asyncio
import math
from fastapi.testclient import TestClient

from app.main import app
from app.services.analytics import (
    AnalyticsEngine,
    build_daily_trends,
    compute_potential_shortfall,
)
from app.services.data_loader import DataLoaderService
from app.core.cache import get_cache
from app.core.config import get_settings


def test_independent_metric_reconciliation_january_2026():
    """P7-03: Independently compute metrics and reconcile with API and engine."""
    # 1. Load actuals and forecasts
    async def _load():
        settings = get_settings()
        cache = get_cache()
        loader = DataLoaderService(cache=cache, settings=settings, use_fixtures=True)
        actuals, _, _ = await loader.get_january_actuals()
        forecasts, _, _ = await loader.get_january_forecasts()
        return actuals, forecasts

    actuals, forecasts = asyncio.run(_load())

    # 2. Align under 12:00 D-1 cutoff
    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month="2026-01",
        cutoff_time="12:00",
    )

    matched = [item for item in aligned if item.status == "matched"]
    assert len(matched) == 1488

    # 3. Independent manual calculations in pure Python (no engine calls)
    n = len(matched)
    manual_abs_errors = []
    manual_sq_errors = []
    manual_signed_errors = []
    manual_actual_sum = 0.0
    manual_shortfall_mwh = 0.0

    for item in matched:
        f = item.forecast_mw
        a = item.actual_mw
        err = f - a
        abs_err = abs(err)

        manual_signed_errors.append(err)
        manual_abs_errors.append(abs_err)
        manual_sq_errors.append(err ** 2)
        manual_actual_sum += a

        if err > 0:
            manual_shortfall_mwh += err * 0.5  # 30-min interval: MW * 0.5h = MWh

    manual_mae = sum(manual_abs_errors) / n
    manual_rmse = math.sqrt(sum(manual_sq_errors) / n)
    manual_bias = sum(manual_signed_errors) / n
    manual_wape = (sum(manual_abs_errors) / manual_actual_sum) * 100.0

    # 4. Compare with AnalyticsEngine output
    summary = AnalyticsEngine.compute_metrics(matched)

    assert abs(summary.mae - round(manual_mae, 2)) < 1e-6
    assert abs(summary.rmse - round(manual_rmse, 2)) < 1e-6
    assert abs(summary.bias - round(manual_bias, 2)) < 1e-6
    assert abs(summary.wape - round(manual_wape, 2)) < 1e-6

    # Potential shortfall comparison
    shortfall_mwh, count, max_single = compute_potential_shortfall(matched)
    assert abs(shortfall_mwh - round(manual_shortfall_mwh, 1)) < 1e-6

    # 5. Query /api/v1/overview via TestClient and reconcile
    with TestClient(app) as client:
        resp = client.get("/api/v1/overview?month=2026-01&cutoff=12:00")
        assert resp.status_code == 200
        data = resp.json()

        assert round(data["mae"], 2) == round(manual_mae, 2)
        assert round(data["rmse"], 2) == round(manual_rmse, 2)
        assert round(data["bias"], 2) == round(manual_bias, 2)
        assert round(data["wape"], 2) == round(manual_wape, 2)
        assert round(data["potential_shortfall_mwh"], 1) == round(manual_shortfall_mwh, 1)


def test_independent_single_day_reconciliation_jan_12():
    """P7-03: Manually reconcile Day 12 (Peak Storm Miss Day, 48 intervals)."""
    async def _load():
        settings = get_settings()
        cache = get_cache()
        loader = DataLoaderService(cache=cache, settings=settings, use_fixtures=True)
        actuals, _, _ = await loader.get_january_actuals()
        forecasts, _, _ = await loader.get_january_forecasts()
        return actuals, forecasts

    actuals, forecasts = asyncio.run(_load())

    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month="2026-01",
        cutoff_time="12:00",
    )

    day12_items = [i for i in aligned if i.settlement_date == "2026-01-12" and i.status == "matched"]
    assert len(day12_items) == 48

    # Manual calculations
    manual_abs = [abs(i.forecast_mw - i.actual_mw) for i in day12_items]
    manual_sq = [(i.forecast_mw - i.actual_mw) ** 2 for i in day12_items]
    manual_signed = [i.forecast_mw - i.actual_mw for i in day12_items]
    manual_actual_sum = sum(i.actual_mw for i in day12_items)
    manual_shortfall = sum(max(0.0, i.forecast_mw - i.actual_mw) * 0.5 for i in day12_items)

    d12_mae = sum(manual_abs) / 48
    d12_rmse = math.sqrt(sum(manual_sq) / 48)
    d12_bias = sum(manual_signed) / 48
    d12_wape = (sum(manual_abs) / manual_actual_sum) * 100.0

    # Engine daily trend comparison
    daily_trends = build_daily_trends(aligned)
    d12_trend = next(d for d in daily_trends if d.date == "2026-01-12")

    assert abs(d12_trend.mae - round(d12_mae, 2)) < 1e-6
    assert abs(d12_trend.rmse - round(d12_rmse, 2)) < 1e-6
    assert abs(d12_trend.bias - round(d12_bias, 2)) < 1e-6
    assert abs(d12_trend.wape - round(d12_wape, 2)) < 1e-6
    assert abs(d12_trend.shortfall_mwh - round(manual_shortfall, 1)) < 1e-6
