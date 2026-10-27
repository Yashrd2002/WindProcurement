from typing import List, Optional
from pydantic import BaseModel, Field


class AiBriefingRequest(BaseModel):
    """Payload to request an AI-generated trading desk morning briefing."""

    month: str = Field(default="2026-01", description="Target evaluation month (YYYY-MM)")
    cutoff: str = Field(default="12:00", description="Day-ahead auction cutoff time on Day D-1")
    risk_tolerance: str = Field(
        default="balanced",
        description="Desk risk appetite: 'conservative' (higher thermal buffer), 'balanced', or 'aggressive'",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional OpenAI API key override (if not set in server environment)",
    )
    custom_query: Optional[str] = Field(
        default=None,
        description="Optional prompt question or focus area from the trader",
    )


class HedgingRecommendation(BaseModel):
    """Recommended thermal capacity buffer to purchase in day-ahead wholesale auction."""

    recommended_thermal_buffer_mw: float = Field(
        description="Recommended additional thermal generation (MW) to procure above unadjusted wind forecast"
    )
    strategy_rationale: str = Field(
        description="Detailed procurement justification accounting for systematic overforecast bias and cashout risk"
    )
    risk_level: str = Field(
        description="Overall desk exposure risk level: High, Elevated, or Moderate"
    )
    unhedged_shortfall_mwh: float = Field(
        description="Volume of energy (MWh) exposed to balancing cashout if unhedged"
    )


class PeakExposureAlert(BaseModel):
    """Specific high-volatility interval posing extreme imbalance cashout risk."""

    interval_id: str = Field(description="Interval identifier (e.g. 2026-01-12-SP03)")
    settlement_date: str = Field(description="Settlement date (YYYY-MM-DD)")
    settlement_period: int = Field(description="Settlement period (1-48)")
    forecast_mw: float = Field(description="Operational day-ahead forecast in MW")
    actual_mw: float = Field(description="Realized Elexon wind generation in MW")
    error_mw: float = Field(description="Signed forecasting error (Forecast - Actual) in MW")
    shortfall_mwh: float = Field(description="Physical energy deficit in MWh")
    risk_category: str = Field(description="Operational risk driver (e.g. Storm Cut-Out Ramp, High-Pressure Calm)")
    mitigation_action: str = Field(description="Immediate procurement desk countermeasure")


class AiBriefingResponse(BaseModel):
    """Complete AI Trading Desk Morning Briefing & Sizing Directive."""

    executive_summary: str = Field(
        description="High-level commercial summary of wind fleet predictability and systematic error regime"
    )
    hedging_recommendation: HedgingRecommendation = Field(
        description="Specific thermal procurement sizing directives for the day-ahead auction"
    )
    peak_exposure_alerts: List[PeakExposureAlert] = Field(
        default_factory=list,
        description="Key danger intervals with extreme shortfall exposure"
    )
    operational_checklist: List[str] = Field(
        default_factory=list,
        description="Actionable 3-point protocol for power traders during the active trading shift"
    )
    market_context: str = Field(
        description="UK balancing mechanism regulatory context (12:00 D-1 auction rules and cashout price exposure)"
    )
    ai_provider: str = Field(
        description="Provider executing the analysis: 'openai' or 'deterministic-expert-fallback'"
    )
    model_used: Optional[str] = Field(
        default=None,
        description="Name of the underlying LLM model (e.g. gpt-4o-mini) if called"
    )
    timestamp_utc: str = Field(
        description="ISO 8601 UTC generation timestamp"
    )
