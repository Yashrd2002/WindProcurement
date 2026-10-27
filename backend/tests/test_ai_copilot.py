import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
import httpx

from app.main import app
from app.schemas.ai import AiBriefingRequest, AiBriefingResponse
from app.services.ai_copilot import AiCopilotService
from app.schemas.overview import OverviewResponse, LargestErrorInterval, MetricCard


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_ai_briefing_endpoint(client):
    """Verify POST /api/v1/ai/briefing generates structured intelligence."""
    response = client.post(
        "/api/v1/ai/briefing",
        json={
            "month": "2026-01",
            "cutoff": "12:00",
            "risk_tolerance": "balanced",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ai_provider"] in ["openai", "deterministic-expert-fallback"]
    assert "hedging_recommendation" in data
    rec = data["hedging_recommendation"]
    assert rec["recommended_thermal_buffer_mw"] > 1000.0
    assert rec["risk_level"] in ["High", "Elevated", "Moderate"]
    assert len(data["peak_exposure_alerts"]) >= 1
    assert len(data["operational_checklist"]) >= 3
    assert "executive_summary" in data
    assert "timestamp_utc" in data


def test_ai_briefing_risk_tolerance_scaling():
    """Verify conservative tolerance recommends higher thermal hedge buffer than aggressive."""
    dummy_overview = OverviewResponse(
        target_month="2026-01",
        cutoff_time="12:00",
        mae=2020.64,
        rmse=2481.38,
        bias=1806.23,
        wape=17.45,
        potential_shortfall_mwh=1423598.0,
        total_actual_generation_mwh=4308034.25,
        completeness_pct=100.0,
        total_expected_intervals=1488,
        total_matched_intervals=1488,
        missing_actual_intervals=0,
        missing_forecast_intervals=0,
        data_status="complete",
        cards=[],
        daily_trends=[],
        largest_errors=[],
    )
    res_cons = AiCopilotService._generate_deterministic_briefing(
        AiBriefingRequest(risk_tolerance="conservative"), dummy_overview, []
    )
    res_aggr = AiCopilotService._generate_deterministic_briefing(
        AiBriefingRequest(risk_tolerance="aggressive"), dummy_overview, []
    )
    buf_cons = res_cons.hedging_recommendation.recommended_thermal_buffer_mw
    buf_aggr = res_aggr.hedging_recommendation.recommended_thermal_buffer_mw
    assert buf_cons > buf_aggr


def test_ai_briefing_forced_fallback():
    """Verify deterministic fallback when openai_api_key is explicitly None."""
    from app.core.config import Settings
    dummy_settings = Settings(openai_api_key=None)
    req = AiBriefingRequest(month="2026-01", cutoff="12:00", risk_tolerance="balanced")
    dummy_overview = OverviewResponse(
        target_month="2026-01",
        cutoff_time="12:00",
        mae=2020.64,
        rmse=2481.38,
        bias=1806.23,
        wape=17.45,
        potential_shortfall_mwh=1423598.0,
        total_actual_generation_mwh=4308034.25,
        completeness_pct=100.0,
        total_expected_intervals=1488,
        total_matched_intervals=1488,
        missing_actual_intervals=0,
        missing_forecast_intervals=0,
        data_status="complete",
        cards=[],
        daily_trends=[],
        largest_errors=[],
    )
    import asyncio
    async def _run():
        mock_client = AsyncMock()
        return await AiCopilotService.generate_briefing(
            request=req,
            overview=dummy_overview,
            largest_errors=[],
            http_client=mock_client,
            settings=dummy_settings,
        )
    res = asyncio.run(_run())
    assert res.ai_provider == "deterministic-expert-fallback"
    assert res.hedging_recommendation.recommended_thermal_buffer_mw == 1806.2


def test_ai_copilot_service_mock_openai():
    """Verify OpenAI chat response is successfully parsed into AiBriefingResponse."""
    async def _run():
        mock_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "executive_summary": "Wind fleet demonstrated severe systematic overforecasting during January 2026.",
                            "hedging_recommendation": {
                                "recommended_thermal_buffer_mw": 2100.0,
                                "strategy_rationale": "Procure 2,100 MW of CCGT capacity in day-ahead auction to hedge imbalance.",
                                "risk_level": "High",
                                "unhedged_shortfall_mwh": 1423598.0,
                            },
                            "peak_exposure_alerts": [
                                {
                                    "interval_id": "2026-01-12-SP03",
                                    "settlement_date": "2026-01-12",
                                    "settlement_period": 3,
                                    "forecast_mw": 14200.0,
                                    "actual_mw": 7315.0,
                                    "error_mw": 6885.0,
                                    "shortfall_mwh": 3442.5,
                                    "risk_category": "Storm Cut-Out Ramp",
                                    "mitigation_action": "Trigger Fast Reserve",
                                }
                            ],
                            "operational_checklist": [
                                "1. Size day-ahead thermal hedge at +2,100 MW.",
                                "2. Watch Storm Gorel ramp periods.",
                                "3. Monitor SBP cashout prices.",
                            ],
                            "market_context": "UK day-ahead 12:00 D-1 auction gate closure context.",
                        })
                    }
                }
            ]
        }

        mock_resp = httpx.Response(200, json=mock_payload, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        from app.core.config import Settings
        test_settings = Settings(openai_api_key="test-key-mock", openai_model="gpt-4o-mini")
        req = AiBriefingRequest(month="2026-01", cutoff="12:00", risk_tolerance="balanced")
        dummy_overview = OverviewResponse(
            target_month="2026-01",
            cutoff_time="12:00",
            mae=2020.64,
            rmse=2481.38,
            bias=1806.23,
            wape=17.45,
            potential_shortfall_mwh=1423598.0,
            total_actual_generation_mwh=4308034.25,
            completeness_pct=100.0,
            total_expected_intervals=1488,
            total_matched_intervals=1488,
            missing_actual_intervals=0,
            missing_forecast_intervals=0,
            data_status="complete",
            cards=[],
            daily_trends=[],
            largest_errors=[],
        )

        return await AiCopilotService.generate_briefing(
            request=req,
            overview=dummy_overview,
            largest_errors=[],
            http_client=mock_client,
            settings=test_settings,
        )

    import asyncio
    result = asyncio.run(_run())
    assert result.ai_provider == "openai"
    assert result.model_used == "gpt-4o-mini"
    assert result.hedging_recommendation.recommended_thermal_buffer_mw == 2100.0
    assert len(result.peak_exposure_alerts) == 1
    assert result.peak_exposure_alerts[0].interval_id == "2026-01-12-SP03"


def test_ai_copilot_service_upstream_error_graceful_fallback():
    """Verify service falls back to deterministic briefing if OpenAI fails or times out."""
    async def _run():
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectTimeout("OpenAI connection timed out")

        from app.core.config import Settings
        test_settings = Settings(openai_api_key="sk-live-test", openai_model="gpt-4o-mini")
        req = AiBriefingRequest(month="2026-01", cutoff="12:00", risk_tolerance="balanced")
        dummy_overview = OverviewResponse(
            target_month="2026-01",
            cutoff_time="12:00",
            mae=2020.64,
            rmse=2481.38,
            bias=1806.23,
            wape=17.45,
            potential_shortfall_mwh=1423598.0,
            total_actual_generation_mwh=4308034.25,
            completeness_pct=100.0,
            total_expected_intervals=1488,
            total_matched_intervals=1488,
            missing_actual_intervals=0,
            missing_forecast_intervals=0,
            data_status="complete",
            cards=[],
            daily_trends=[],
            largest_errors=[],
        )

        return await AiCopilotService.generate_briefing(
            request=req,
            overview=dummy_overview,
            largest_errors=[],
            http_client=mock_client,
            settings=test_settings,
        )

    import asyncio
    result = asyncio.run(_run())
    assert result.ai_provider == "deterministic-expert-fallback"
    assert result.hedging_recommendation.recommended_thermal_buffer_mw > 1000.0
