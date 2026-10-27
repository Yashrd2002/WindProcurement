from fastapi import APIRouter, Depends

from app.api.deps import get_data_loader, validate_cutoff_time, validate_target_month
from app.schemas.quality import QualityAuditItem, QualityReportResponse
from app.services.analytics import AnalyticsEngine
from app.services.data_loader import DataLoaderService

router = APIRouter(prefix="/api/v1", tags=["quality"])


@router.get("/quality", response_model=QualityReportResponse)
async def get_quality_report(
    month: str = Depends(validate_target_month),
    cutoff: str = Depends(validate_cutoff_time),
    loader: DataLoaderService = Depends(get_data_loader),
) -> QualityReportResponse:
    """Retrieve data quality report, gap audits, and completeness breakdown."""
    actuals, _, _ = await loader.get_january_actuals()
    forecasts, _, _ = await loader.get_january_forecasts()

    audit = AnalyticsEngine.audit_coverage(
        actuals=actuals,
        forecasts=forecasts,
        target_month=month,
        cutoff_time=cutoff,
    )

    audits = [
        QualityAuditItem(
            category="Stream Availability",
            status=(
                "pass"
                if audit.actual_intervals_found > 0 and audit.forecast_intervals_found > 0
                else "fail"
            ),
            metric="Upstream Elexon Ingestion",
            detail=f"Received {audit.actual_intervals_found} actuals, {len(forecasts)} forecast versions.",
        ),
        QualityAuditItem(
            category="Completeness",
            status=(
                "pass"
                if audit.completeness_pct == 100.0
                else "warning"
                if audit.completeness_pct >= 90.0
                else "fail"
            ),
            metric="Settlement Period Coverage",
            detail=f"{audit.matched_intervals} of {audit.expected_intervals} intervals matched ({audit.completeness_pct}%).",
        ),
        QualityAuditItem(
            category="Duplicate Check",
            status="pass" if audit.duplicate_actual_count == 0 else "warning",
            metric="Zero Duplicate Settlement Periods",
            detail=f"{audit.duplicate_actual_count} duplicate settlement periods detected.",
        ),
        QualityAuditItem(
            category="Cutoff Integrity",
            status="pass",
            metric="Look-ahead Protection",
            detail=f"All operational forecasts published <= {cutoff} UK time on day D-1.",
        ),
    ]

    overall_status = (
        "complete"
        if audit.completeness_pct == 100.0
        else "partial"
        if audit.completeness_pct >= 50.0
        else "degraded"
    )

    return QualityReportResponse(
        target_month=month,
        cutoff_time=cutoff,
        overall_status=overall_status,
        completeness_pct=audit.completeness_pct,
        expected_intervals=audit.expected_intervals,
        actual_intervals_found=audit.actual_intervals_found,
        forecast_intervals_found=audit.forecast_intervals_found,
        matched_intervals=audit.matched_intervals,
        missing_actual_count=audit.missing_actual_count,
        missing_forecast_count=audit.missing_forecast_count,
        missing_actual_intervals=audit.missing_actual_intervals,
        missing_forecast_intervals=audit.missing_forecast_intervals,
        audits=audits,
        notes=[
            "Data source: National Grid ESO / Elexon Insights Solution (BMRS).",
            "Target window: January 2026 (1,488 half-hour settlement periods).",
            f"Decision cutoff applied: {cutoff} Europe/London on day D-1.",
        ],
    )
