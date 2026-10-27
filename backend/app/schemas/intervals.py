from typing import List, Optional
from pydantic import BaseModel, Field


class IntervalItem(BaseModel):
    interval_id: str = Field(description="Unique identifier: YYYY-MM-DD-SP (e.g. 2026-01-01-01)")
    start_time: str
    settlement_date: str
    settlement_period: int

    actual_mw: Optional[float] = None
    forecast_mw: Optional[float] = None
    error_mw: Optional[float] = None
    shortfall_mwh: Optional[float] = None

    forecast_publish_time: Optional[str] = None
    cutoff_time_applied: str
    status: str


class IntervalsResponse(BaseModel):
    target_month: str
    cutoff_time: str
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[IntervalItem]
