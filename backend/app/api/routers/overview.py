from fastapi import APIRouter, Depends

from app.api.deps import get_data_loader, validate_cutoff_time, validate_target_month
from app.schemas.overview import MetricCard, OverviewResponse
from app.services.analytics import AnalyticsEngine
from app.services.data_loader import DataLoaderService

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    month: str = Depends(validate_target_month),
    cutoff: str = Depends(validate_cutoff_time),
    loader: DataLoaderService = Depends(get_data_loader),
) -> OverviewResponse:
    """Retrieve aggregate KPI accuracy and shortfall metrics for the given month and cutoff."""
    actuals, _, _ = await loader.get_january_actuals()
    forecasts, _, _ = await loader.get_january_forecasts()
    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month=month,
        cutoff_time=cutoff,
    )
    metrics = AnalyticsEngine.compute_metrics(aligned)

    total_expected = len(aligned)
    matched_count = sum(1 for i in aligned if i.status == "matched")
    missing_actual_count = sum(1 for i in aligned if i.status == "missing_actual")
    missing_forecast_count = sum(1 for i in aligned if i.status == "missing_forecast")

    completeness_pct = round((matched_count / total_expected) * 100.0, 1) if total_expected > 0 else 0.0

    # Shortfall volume (MWh): max(F-A, 0) * 0.5h
    shortfall_mwh = round(sum(i.shortfall_mwh or 0.0 for i in aligned), 2)
    # Total actual generation in MWh: MW * 0.5h
    total_actual_mwh = round(metrics.total_actual_mw * 0.5, 2)

    # Data status classification
    if matched_count == total_expected:
        data_status = "complete"
    elif matched_count > 0:
        data_status = "partial"
    else:
        data_status = "empty"

    cards = [
        MetricCard(
            key="mae",
            label="Mean Absolute Error",
            value=metrics.mae,
            unit="MW",
            formatted=f"{metrics.mae:,.1f} MW" if metrics.mae is not None else "N/A",
            description="Average deviation magnitude between forecast and actuals",
            sample_count=metrics.sample_count,
            interpretation="Lower indicates tighter overall day-ahead sizing.",
        ),
        MetricCard(
            key="rmse",
            label="Root Mean Squared Error",
            value=metrics.rmse,
            unit="MW",
            formatted=f"{metrics.rmse:,.1f} MW" if metrics.rmse is not None else "N/A",
            description="Magnitude-penalized error emphasizing large forecasting misses",
            sample_count=metrics.sample_count,
            interpretation="Penalizes large swings that trigger emergency dispatch.",
        ),
        MetricCard(
            key="bias",
            label="Systematic Forecast Bias",
            value=metrics.bias,
            unit="MW",
            formatted=(
                f"{'+' if metrics.bias > 0 else ''}{metrics.bias:,.1f} MW"
                if metrics.bias is not None
                else "N/A"
            ),
            description="Signed mean error: positive indicates overforecasting tendency",
            sample_count=metrics.sample_count,
            interpretation=(
                "Overforecast (F > A)"
                if metrics.bias and metrics.bias > 0
                else "Underforecast (F < A)"
                if metrics.bias and metrics.bias < 0
                else "Balanced"
            ),
        ),
        MetricCard(
            key="wape",
            label="Volume-Weighted Error (WAPE)",
            value=metrics.wape,
            unit="%",
            formatted=f"{metrics.wape:.1f}%" if metrics.wape is not None else "N/A",
            description="Aggregate absolute error divided by total realized generation",
            sample_count=metrics.sample_count,
            interpretation="Standard industry normalized accuracy benchmark.",
        ),
        MetricCard(
            key="shortfall",
            label="Potential Shortfall Volume",
            value=shortfall_mwh,
            unit="MWh",
            formatted=f"{shortfall_mwh:,.1f} MWh",
            description="Cumulative volume of unanticipated generation shortfalls",
            sample_count=metrics.sample_count,
            interpretation="Volume requiring replacement by day-ahead thermal power.",
        ),
        MetricCard(
            key="completeness",
            label="Data Completeness",
            value=completeness_pct,
            unit="%",
            formatted=f"{completeness_pct:.1f}%",
            description="Valid matched intervals divided by scheduled intervals",
            sample_count=total_expected,
            interpretation=f"{matched_count} of {total_expected} settlement periods matched.",
        ),
    ]

    from app.services.analytics import build_daily_trends, find_largest_error_intervals

    daily_trends = build_daily_trends(aligned)
    largest_errors = find_largest_error_intervals(aligned, limit=5)

    return OverviewResponse(
        target_month=month,
        cutoff_time=cutoff,
        mae=metrics.mae,
        rmse=metrics.rmse,
        bias=metrics.bias,
        wape=metrics.wape,
        potential_shortfall_mwh=shortfall_mwh,
        total_actual_generation_mwh=total_actual_mwh,
        completeness_pct=completeness_pct,
        total_expected_intervals=total_expected,
        total_matched_intervals=matched_count,
        missing_actual_intervals=missing_actual_count,
        missing_forecast_intervals=missing_forecast_count,
        data_status=data_status,
        cards=cards,
        daily_trends=daily_trends,
        largest_errors=largest_errors,
    )
