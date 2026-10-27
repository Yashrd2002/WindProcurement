from typing import List, Optional
from pydantic import BaseModel, Field


class MetricCard(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    unit: str
    formatted: str
    description: str
    sample_count: int
    interpretation: Optional[str] = None


class DailyTrendItem(BaseModel):
    """Daily aggregated metrics and energy volumes for trend tracking (P5-07)."""

    date: str = Field(description="Delivery date (YYYY-MM-DD)")
    matched_intervals: int = Field(description="Matched settlement periods in day")
    expected_intervals: int = Field(default=48, description="Expected periods in day")
    mae: Optional[float] = Field(None, description="Day MAE in MW")
    rmse: Optional[float] = Field(None, description="Day RMSE in MW")
    bias: Optional[float] = Field(None, description="Day Signed Bias in MW")
    wape: Optional[float] = Field(None, description="Day WAPE in %")
    shortfall_mwh: float = Field(default=0.0, description="Cumulative day shortfall in MWh")
    actual_generation_mwh: float = Field(default=0.0, description="Realized wind generation in MWh")
    forecast_generation_mwh: float = Field(default=0.0, description="Forecast wind generation in MWh")


class LargestErrorInterval(BaseModel):
    """Extreme forecasting error interval highlighting operational risk periods (P5-07)."""

    interval_id: str = Field(description="Interval identifier: YYYY-MM-DD-SP")
    start_time: str = Field(description="Delivery interval start timestamp (UTC)")
    settlement_date: str = Field(description="Settlement date (YYYY-MM-DD)")
    settlement_period: int = Field(description="Settlement period (1-48)")
    actual_mw: float = Field(description="Realized generation in MW")
    forecast_mw: float = Field(description="Cutoff forecast in MW")
    error_mw: float = Field(description="Signed forecast error: Forecast - Actual in MW")
    abs_error_mw: float = Field(description="Absolute forecasting deviation in MW")
    shortfall_mwh: float = Field(description="Shortfall volume in MWh")
    direction: str = Field(description="Direction of error: overforecast | underforecast")


class OverviewResponse(BaseModel):
    """Aggregate KPI overview metrics for the chosen analysis window and cutoff."""

    target_month: str = Field(description="Delivery target month YYYY-MM")
    cutoff_time: str = Field(description="Day-ahead cutoff time (HH:MM) on Day D-1")
    timezone: str = Field(default="Europe/London")

    # Core statistical metrics (ADR-04 & Metric Definitions)
    mae: Optional[float] = Field(None, description="Mean Absolute Error in MW")
    rmse: Optional[float] = Field(None, description="Root Mean Squared Error in MW")
    bias: Optional[float] = Field(None, description="Signed Mean Error (Forecast - Actual) in MW")
    wape: Optional[float] = Field(None, description="Weighted Absolute Percentage Error in %")
    potential_shortfall_mwh: Optional[float] = Field(
        None, description="Cumulative volume of unanticipated renewable shortfalls (MWh)"
    )
    total_actual_generation_mwh: Optional[float] = Field(
        None, description="Total realized wind generation in MWh"
    )

    # Coverage and data completeness
    completeness_pct: float = Field(description="Percentage of valid matched settlement intervals")
    total_expected_intervals: int = Field(default=1488, description="Expected intervals in target month")
    total_matched_intervals: int = Field(description="Successfully matched intervals")
    missing_actual_intervals: int = Field(default=0, description="Intervals missing realized actuals")
    missing_forecast_intervals: int = Field(default=0, description="Intervals missing eligible forecasts")

    data_status: str = Field(
        default="complete", description="Data quality classification: complete | partial | empty"
    )
    cards: List[MetricCard] = Field(default_factory=list, description="Preformatted KPI cards for frontend")
    daily_trends: List[DailyTrendItem] = Field(default_factory=list, description="Day-by-day aggregated metrics (P5-07)")
    largest_errors: List[LargestErrorInterval] = Field(default_factory=list, description="Top 5 largest error intervals (P5-07)")
