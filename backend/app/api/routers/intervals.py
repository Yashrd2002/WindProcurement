from datetime import date, datetime
import math
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_data_loader,
    validate_cutoff_time,
    validate_date_range,
    validate_pagination,
    validate_target_month,
)
from app.schemas.intervals import IntervalItem, IntervalsResponse
from app.services.analytics import AnalyticsEngine
from app.services.data_loader import DataLoaderService

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/intervals", response_model=IntervalsResponse)
async def get_intervals(
    month: str = Depends(validate_target_month),
    cutoff: str = Depends(validate_cutoff_time),
    date_range: tuple[date, date] = Depends(validate_date_range),
    pagination: tuple[int, int] = Depends(validate_pagination),
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by interval status: matched | missing_forecast | missing_actual",
    ),
    loader: DataLoaderService = Depends(get_data_loader),
) -> IntervalsResponse:
    """Retrieve paginated half-hour settlement period records."""
    page, page_size = pagination
    start_date, end_date = date_range

    actuals, _, _ = await loader.get_january_actuals()
    forecasts, _, _ = await loader.get_january_forecasts()
    aligned = AnalyticsEngine.align_intervals(
        actuals=actuals,
        forecasts=forecasts,
        target_month=month,
        cutoff_time=cutoff,
    )

    # Filter by date range
    filtered = [
        item
        for item in aligned
        if start_date
        <= datetime.strptime(item.settlement_date, "%Y-%m-%d").date()
        <= end_date
    ]

    # Filter by status if requested
    if status_filter:
        filtered = [item for item in filtered if item.status == status_filter]

    total = len(filtered)
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = filtered[start_idx:end_idx]

    items = [
        IntervalItem(
            interval_id=item.interval_id,
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
            cutoff_time_applied=item.cutoff_time_applied.isoformat(),
            status=item.status,
        )
        for item in page_items
    ]

    return IntervalsResponse(
        target_month=month,
        cutoff_time=cutoff,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )
