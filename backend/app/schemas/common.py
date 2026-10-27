from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class IntervalStatus(str, Enum):
    MATCHED = "matched"
    MISSING_FORECAST = "missing_forecast"
    MISSING_ACTUAL = "missing_actual"
    UNMATCHED = "unmatched"


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    error_type: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    request_id: Optional[str] = None
    errors: Optional[List[ErrorDetail]] = None


class CutoffPolicyInfo(BaseModel):
    cutoff_time: str = Field(default="12:00", description="HH:MM UK cutoff time on Day D-1")
    timezone: str = Field(default="Europe/London", description="Timezone of the decision desk")
    day_offset: int = Field(default=-1, description="Day offset relative to delivery date (D-1)")
    description: str = Field(
        default="Selects the latest forecast published on or before 12:00 UK time on day D-1"
    )
