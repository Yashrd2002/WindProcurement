from fastapi import APIRouter, Depends

from app.api.deps import get_data_loader, validate_cutoff_time, validate_target_month
from app.schemas.timeseries import TimeseriesPoint, TimeseriesResponse
from app.services.analytics import AnalyticsEngine
from app.services.data_loader import DataLoaderService

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/timeseries", response_model=TimeseriesResponse)
async def get_timeseries(
    month: str = Depends(validate_target_month),
    cutoff: str = Depends(validate_cutoff_time),
    loader: DataLoaderService = Depends(get_data_loader),
) -> TimeseriesResponse:
    """Retrieve time-aligned actual vs cutoff-selected forecast series for chart rendering."""
    actuals, _, _ = await loader.get_january_actuals()
    forecasts, _, _ = await loader.get_january_forecasts()
    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month=month,
        cutoff_time=cutoff,
    )

    points = [
        TimeseriesPoint(
            start_time=item.start_time.isoformat(),
            settlement_date=item.settlement_date,
            settlement_period=item.settlement_period,
            actual_mw=item.actual_mw,
            forecast_mw=item.forecast_mw,
            error_mw=item.error_mw,
            shortfall_mwh=item.shortfall_mwh,
            forecast_publish_time=(
                item.forecast_publish_time.isoformat()
                if item.forecast_publish_time
                else None
            ),
            status=item.status,
        )
        for item in aligned
    ]
    matched_points = sum(1 for p in points if p.status == "matched")

    return TimeseriesResponse(
        target_month=month,
        cutoff_time=cutoff,
        total_points=len(points),
        matched_points=matched_points,
        points=points,
    )
