from datetime import datetime, timezone
import pytest

from app.services.normalization import RecordNormalizer


def test_normalize_valid_fuelhh_record() -> None:
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": 14500.5,
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is not None
    assert rejection is None
    assert record.generation_mw == 14500.5
    assert record.settlement_period == 2
    assert record.publish_time == datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert record.start_time == datetime(2026, 1, 1, 0, 30, 0, tzinfo=timezone.utc)


def test_normalize_valid_zero_generation() -> None:
    """True zero generation is valid (calm wind) and distinct from missing data."""
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": 0,
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is not None
    assert record.generation_mw == 0.0


def test_reject_fuelhh_missing_required_fields() -> None:
    raw = {
        "dataset": "FUELHH",
        "startTime": "2026-01-01T00:30:00Z",
        # Missing publishTime, settlementPeriod, etc.
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is None
    assert "Missing required fields" in rejection


def test_reject_negative_generation() -> None:
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": -50.0,
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is None
    assert "Negative generation value" in rejection


def test_reject_invalid_settlement_period() -> None:
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 0,  # Invalid: 1 to 50
        "fuelType": "WIND",
        "generation": 1000.0,
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is None
    assert "out of valid range" in rejection


def test_reject_invalid_date_format() -> None:
    raw = {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "01/01/2026",  # Invalid format (expected YYYY-MM-DD)
        "settlementPeriod": 1,
        "fuelType": "WIND",
        "generation": 1000.0,
    }
    record, rejection = RecordNormalizer.normalize_fuelhh_record(raw)
    assert record is None
    assert "Invalid settlementDate format" in rejection


def test_normalize_valid_windfor_record() -> None:
    raw = {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T11:30:00Z",
        "startTime": "2026-01-02T00:00:00Z",
        "generation": 18200,
    }
    record, rejection = RecordNormalizer.normalize_windfor_record(raw)
    assert record is not None
    assert rejection is None
    assert record.generation_mw == 18200.0
    assert record.publish_time == datetime(2026, 1, 1, 11, 30, 0, tzinfo=timezone.utc)
    assert record.start_time == datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)


def test_reject_windfor_malformed() -> None:
    raw = {
        "dataset": "WINDFOR",
        "publishTime": "invalid-time",
        "startTime": "2026-01-02T00:00:00Z",
        "generation": 18200,
    }
    record, rejection = RecordNormalizer.normalize_windfor_record(raw)
    assert record is None
    assert "Invalid publishTime ISO format" in rejection


def test_normalize_stream_audit_report() -> None:
    items = [
        {"dataset": "FUELHH", "publishTime": "2026-01-01T01:00:00Z", "startTime": "2026-01-01T00:30:00Z", "settlementDate": "2026-01-01", "settlementPeriod": 1, "fuelType": "WIND", "generation": 1000},
        {"dataset": "FUELHH", "broken": True},
        {"dataset": "FUELHH", "publishTime": "2026-01-01T01:00:00Z", "startTime": "2026-01-01T00:30:00Z", "settlementDate": "2026-01-01", "settlementPeriod": 2, "fuelType": "WIND", "generation": -10},
    ]
    records, report = RecordNormalizer.normalize_fuelhh_stream(items, fuel_type_filter="WIND")
    assert len(records) == 1
    assert report.total_received == 3
    assert report.valid_count == 1
    assert report.rejected_count == 2
    assert len(report.rejection_reasons) == 2
