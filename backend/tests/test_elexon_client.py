import asyncio
from datetime import datetime, timezone
from pathlib import Path
import pytest
import httpx

from app.services.elexon_client import (
    ElexonClient,
    ElexonPayloadError,
    ElexonUpstreamError,
    ElexonValidationError,
    format_iso_utc,
)
from app.services.models import ForecastRecord, FuelRecord

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_format_iso_utc() -> None:
    dt = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert format_iso_utc(dt) == "2026-01-01T12:30:00Z"

    str_val = "2026-01-01T12:30:00Z"
    assert format_iso_utc(str_val) == "2026-01-01T12:30:00Z"


def test_parse_fuelhh_record_valid() -> None:
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": 15264,
    }
    client = ElexonClient()
    record = client.parse_fuelhh_record(raw)
    assert record is not None
    assert record.dataset == "FUELHH"
    assert record.fuel_type == "WIND"
    assert record.generation_mw == 15264.0
    assert record.settlement_period == 2
    assert record.settlement_date == "2026-01-01"


def test_parse_fuelhh_stream_filters_wind() -> None:
    raw_stream = [
        {"dataset": "FUELHH", "publishTime": "2026-01-01T01:00:00Z", "startTime": "2026-01-01T00:30:00Z", "settlementDate": "2026-01-01", "settlementPeriod": 2, "fuelType": "NUCLEAR", "generation": 5000},
        {"dataset": "FUELHH", "publishTime": "2026-01-01T01:00:00Z", "startTime": "2026-01-01T00:30:00Z", "settlementDate": "2026-01-01", "settlementPeriod": 2, "fuelType": "WIND", "generation": 14000},
        {"dataset": "FUELHH", "publishTime": "2026-01-01T01:00:00Z", "startTime": "2026-01-01T00:30:00Z", "settlementDate": "2026-01-01", "settlementPeriod": 2, "fuelType": "BIOMASS", "generation": 1200},
    ]
    client = ElexonClient()
    wind_only = client.parse_fuelhh_stream(raw_stream, fuel_type="WIND")
    assert len(wind_only) == 1
    assert wind_only[0].fuel_type == "WIND"
    assert wind_only[0].generation_mw == 14000.0


def test_parse_windfor_record_valid() -> None:
    raw = {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T22:30:00Z",
        "startTime": "2025-12-31T21:00:00Z",
        "generation": 19498,
    }
    client = ElexonClient()
    record = client.parse_windfor_record(raw)
    assert record is not None
    assert record.dataset == "WINDFOR"
    assert record.generation_mw == 19498.0
    assert record.start_time == datetime(2025, 12, 31, 21, 0, 0, tzinfo=timezone.utc)
    assert record.publish_time == datetime(2026, 1, 1, 22, 30, 0, tzinfo=timezone.utc)


def test_parse_malformed_record_safely_skipped() -> None:
    client = ElexonClient()
    assert client.parse_fuelhh_record({"broken": True}) is None
    assert client.parse_windfor_record({"broken": True}) is None


def test_load_fixture_fuelhh_sample() -> None:
    client = ElexonClient()
    fixture_path = FIXTURES_DIR / "fuelhh_sample_success.json"
    records = client.load_fixture_fuelhh(fixture_path)
    assert len(records) == 48
    assert all(r.settlement_date == "2026-01-01" for r in records)
    assert all(r.fuel_type == "WIND" for r in records)


def test_load_fixture_fuelhh_full_month() -> None:
    client = ElexonClient()
    fixture_path = FIXTURES_DIR / "fuelhh_jan2026_wind.json"
    records = client.load_fixture_fuelhh(fixture_path)
    assert len(records) == 1488


def test_load_fixture_windfor_sample() -> None:
    client = ElexonClient()
    fixture_path = FIXTURES_DIR / "windfor_sample_success.json"
    records = client.load_fixture_windfor(fixture_path)
    assert len(records) == 584
    assert all(isinstance(r, ForecastRecord) for r in records)


def test_fetch_fuelhh_stream_mock() -> None:
    async def run_test() -> None:
        mock_payload = [
            {
                "dataset": "FUELHH",
                "publishTime": "2026-01-01T01:00:00Z",
                "startTime": "2026-01-01T00:30:00Z",
                "settlementDate": "2026-01-01",
                "settlementPeriod": 2,
                "fuelType": "WIND",
                "generation": 12500,
            }
        ]

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "/datasets/FUELHH/stream" in request.url.path
            assert "publishDateTimeFrom=2026-01-01T00%3A00%3A00Z" in str(request.url)
            return httpx.Response(200, json=mock_payload)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            records = await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
            assert len(records) == 1
            assert records[0].generation_mw == 12500.0

    asyncio.run(run_test())


def test_fetch_windfor_stream_mock() -> None:
    async def run_test() -> None:
        mock_payload = [
            {
                "dataset": "WINDFOR",
                "publishTime": "2026-01-01T11:30:00Z",
                "startTime": "2026-01-02T00:00:00Z",
                "generation": 18000,
            }
        ]

        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "/datasets/WINDFOR/stream" in request.url.path
            return httpx.Response(200, json=mock_payload)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            records = await client.fetch_windfor_stream("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
            assert len(records) == 1
            assert records[0].generation_mw == 18000.0

    asyncio.run(run_test())


def test_fetch_fuelhh_validation_error_400() -> None:
    async def run_test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"errors": {"PublishDateTimeFrom": ["DateTime should be in ISO format"]}},
                headers={"content-type": "application/json"},
            )

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            with pytest.raises(ElexonValidationError) as exc_info:
                await client.fetch_fuelhh_stream("invalid-date", "invalid-date")
            assert "Elexon validation error" in str(exc_info.value)

    asyncio.run(run_test())


def test_fetch_fuelhh_upstream_error_500() -> None:
    async def run_test() -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="Bad Gateway")

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://data.elexon.co.uk/bmrs/api/v1") as http_client:
            client = ElexonClient(http_client=http_client)
            with pytest.raises(ElexonUpstreamError) as exc_info:
                await client.fetch_fuelhh_stream("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
            assert exc_info.value.status_code == 502

    asyncio.run(run_test())
