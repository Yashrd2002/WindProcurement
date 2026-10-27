from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FuelRecord(BaseModel):
    """Normalized half-hourly actual fuel generation record (FUELHH)."""

    dataset: str = "FUELHH"
    publish_time: datetime = Field(description="Publication timestamp (UTC)")
    start_time: datetime = Field(description="Delivery interval start timestamp (UTC)")
    settlement_date: str = Field(description="Settlement date (YYYY-MM-DD)")
    settlement_period: int = Field(ge=1, le=50, description="Settlement period index (1-48)")
    fuel_type: str = Field(description="Fuel classification (e.g. WIND)")
    generation_mw: float = Field(description="Average power generated over 30-min period in MW")

    model_config = ConfigDict(frozen=True)


class ForecastRecord(BaseModel):
    """Normalized wind generation forecast record (WINDFOR)."""

    dataset: str = "WINDFOR"
    publish_time: datetime = Field(description="Timestamp when forecast was produced/published (UTC)")
    start_time: datetime = Field(description="Target delivery interval start timestamp (UTC)")
    generation_mw: float = Field(description="Forecasted generation in MW")

    model_config = ConfigDict(frozen=True)


class AlignedInterval(BaseModel):
    """Joined half-hourly settlement interval representing forecast vs actual delivery (P5-01)."""

    interval_id: str = Field(description="Unique interval identifier: YYYY-MM-DD-SP (e.g. 2026-01-01-01)")
    start_time: datetime = Field(description="Start time of delivery interval (UTC)")
    settlement_date: str = Field(description="Settlement date (YYYY-MM-DD)")
    settlement_period: int = Field(ge=1, le=50, description="Settlement period index (1-48)")

    actual_mw: Optional[float] = Field(None, description="Actual realized generation in MW (None if missing)")
    forecast_mw: Optional[float] = Field(None, description="Operational forecast in MW available at cutoff")
    forecast_publish_time: Optional[datetime] = Field(None, description="Timestamp of chosen forecast edition (UTC)")
    cutoff_time_applied: datetime = Field(description="Cutoff timestamp applied for day-ahead decision (UTC)")

    error_mw: Optional[float] = Field(None, description="Forecast minus actual in MW (None if unaligned)")
    shortfall_mwh: Optional[float] = Field(None, description="Unanticipated shortfall in MWh: max(F-A, 0) * 0.5")
    status: str = Field(default="matched", description="Status: matched | missing_forecast | missing_actual")

    model_config = ConfigDict(frozen=True)
