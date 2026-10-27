from typing import List
from pydantic import BaseModel, Field


class QualityAuditItem(BaseModel):
    category: str
    status: str = Field(description="pass | warning | fail")
    metric: str
    detail: str


class QualityReportResponse(BaseModel):
    target_month: str
    cutoff_time: str
    overall_status: str = Field(description="complete | partial | degraded")
    completeness_pct: float

    expected_intervals: int = 1488
    actual_intervals_found: int
    forecast_intervals_found: int
    matched_intervals: int

    missing_actual_count: int
    missing_forecast_count: int
    missing_actual_intervals: List[str] = Field(default_factory=list)
    missing_forecast_intervals: List[str] = Field(default_factory=list)

    audits: List[QualityAuditItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
