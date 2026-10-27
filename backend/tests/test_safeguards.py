from datetime import date
from fastapi import HTTPException
import pytest

from app.core.safeguards import (
    MAX_PAGE_SIZE,
    SUPPORTED_MONTH,
    validate_cutoff_safeguard,
    validate_date_range_safeguards,
    validate_month_safeguard,
    validate_pagination_safeguards,
)


def test_valid_month_passes() -> None:
    assert validate_month_safeguard("2026-01") == "2026-01"


def test_unsupported_month_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_month_safeguard("2025-12")
    assert exc_info.value.status_code == 400
    assert "Unsupported analysis month" in exc_info.value.detail


def test_malformed_month_raises_422() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_month_safeguard("2026/01")
    assert exc_info.value.status_code == 422
    assert "Invalid month format" in exc_info.value.detail


def test_valid_cutoff_passes() -> None:
    assert validate_cutoff_safeguard("12:00") == "12:00"
    assert validate_cutoff_safeguard("00:00") == "00:00"
    assert validate_cutoff_safeguard("23:59") == "23:59"


def test_invalid_cutoff_raises_422() -> None:
    for bad in ["24:00", "12:60", "9:00", "invalid"]:
        with pytest.raises(HTTPException) as exc_info:
            validate_cutoff_safeguard(bad)
        assert exc_info.value.status_code == 422
        assert "Invalid cutoff time format" in exc_info.value.detail


def test_valid_date_range_passes() -> None:
    start, end = validate_date_range_safeguards("2026-01-01", "2026-01-10")
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 10)


def test_inverted_date_range_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_date_range_safeguards("2026-01-15", "2026-01-05")
    assert exc_info.value.status_code == 400
    assert "cannot be earlier than start_date" in exc_info.value.detail


def test_date_outside_january_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_date_range_safeguards("2026-01-01", "2026-02-05")
    assert exc_info.value.status_code == 400
    assert "must fall entirely within January 2026" in exc_info.value.detail


def test_pagination_safeguards() -> None:
    p, ps = validate_pagination_safeguards(1, 48)
    assert p == 1
    assert ps == 48

    # page < 1
    with pytest.raises(HTTPException) as exc_info:
        validate_pagination_safeguards(0, 48)
    assert exc_info.value.status_code == 422

    # page_size > MAX_PAGE_SIZE
    with pytest.raises(HTTPException) as exc_info:
        validate_pagination_safeguards(1, MAX_PAGE_SIZE + 1)
    assert exc_info.value.status_code == 422
