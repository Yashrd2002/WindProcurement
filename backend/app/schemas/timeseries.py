from typing import List, Optional
from pydantic import BaseModel, Field


class TimeseriesPoint(BaseModel):
    """Half-hourly settlement period time series record."""

    start_time: str = Field(description="ISO 8601 UTC timestamp of delivery interval start")
    settlement_date: str = Field(description="UK settlement date (YYYY-MM-DD)")
    settlement_period: int = Field(ge=1, le=50, description="Half-hour period index (1-48, or 50 on clock change)")

    actual_mw: Optional[float] = Field(None, description="Actual realized wind generation in MW")
    forecast_mw: Optional[float] = Field(None, description="Operational forecast in MW available at cutoff")
    error_mw: Optional[float] = Field(None, description="Forecast minus actual in MW (positive = overforecast)")
    shortfall_mwh: Optional[float] = Field(
        None, description="Unanticipated shortfall in MWh (max(F-A, 0) * 0.5)"
    )

    forecast_publish_time: Optional[str] = Field(
        None, description="Publication timestamp of the selected forecast"
    )
    status: str = Field(
        default="matched", description="Interval status: matched | missing_forecast | missing_actual"
    )


class TimeseriesResponse(BaseModel):
    target_month: str
    cutoff_time: str
    total_points: int
    matched_points: int
    points: List[TimeseriesPoint]
