import pytest
from pydantic import ValidationError

from app.schemas.common import CutoffPolicyInfo, IntervalStatus
from app.schemas.intervals import IntervalItem, IntervalsResponse
from app.schemas.overview import MetricCard, OverviewResponse
from app.schemas.quality import QualityAuditItem, QualityReportResponse
from app.schemas.timeseries import TimeseriesPoint, TimeseriesResponse


def test_metric_card_instantiation() -> None:
    card = MetricCard(
        key="mae",
        label="Mean Absolute Error",
        value=345.67,
        unit="MW",
        formatted="345.7 MW",
        description="Average error magnitude",
        sample_count=1488,
    )
    assert card.key == "mae"
    assert card.value == 345.67
    assert card.sample_count == 1488


def test_overview_response_schema() -> None:
    overview = OverviewResponse(
        target_month="2026-01",
        cutoff_time="12:00",
        mae=123.4,
        rmse=234.5,
        bias=45.6,
        wape=8.5,
        potential_shortfall_mwh=1250.0,
        total_actual_generation_mwh=15000.0,
        completeness_pct=100.0,
        total_expected_intervals=1488,
        total_matched_intervals=1488,
        missing_actual_intervals=0,
        missing_forecast_intervals=0,
        data_status="complete",
    )
    assert overview.target_month == "2026-01"
    assert overview.mae == 123.4
    assert overview.completeness_pct == 100.0


def test_timeseries_point_validation() -> None:
    point = TimeseriesPoint(
        start_time="2026-01-01T00:00:00Z",
        settlement_date="2026-01-01",
        settlement_period=1,
        actual_mw=15000.0,
        forecast_mw=15200.0,
        error_mw=200.0,
        shortfall_mwh=100.0,
        status="matched",
    )
    assert point.settlement_period == 1
    assert point.error_mw == 200.0

    # Settlement period out of bounds should fail
    with pytest.raises(ValidationError):
        TimeseriesPoint(
            start_time="2026-01-01T00:00:00Z",
            settlement_date="2026-01-01",
            settlement_period=55,  # Invalid
        )


def test_intervals_response_pagination() -> None:
    item = IntervalItem(
        interval_id="2026-01-01-01",
        start_time="2026-01-01T00:00:00Z",
        settlement_date="2026-01-01",
        settlement_period=1,
        actual_mw=10000.0,
        forecast_mw=9500.0,
        error_mw=-500.0,
        shortfall_mwh=0.0,
        cutoff_time_applied="12:00",
        status="matched",
    )
    resp = IntervalsResponse(
        target_month="2026-01",
        cutoff_time="12:00",
        total=1,
        page=1,
        page_size=48,
        total_pages=1,
        items=[item],
    )
    assert len(resp.items) == 1
    assert resp.items[0].interval_id == "2026-01-01-01"


def test_quality_report_schema() -> None:
    audit = QualityAuditItem(
        category="Stream Reachability",
        status="pass",
        metric="FUELHH & WINDFOR",
        detail="HTTP 200 verified",
    )
    report = QualityReportResponse(
        target_month="2026-01",
        cutoff_time="12:00",
        overall_status="complete",
        completeness_pct=100.0,
        expected_intervals=1488,
        actual_intervals_found=1488,
        forecast_intervals_found=1488,
        matched_intervals=1488,
        missing_actual_count=0,
        missing_forecast_count=0,
        audits=[audit],
    )
    assert report.overall_status == "complete"
    assert len(report.audits) == 1
