from datetime import date, datetime
import re
from typing import Optional
from fastapi import HTTPException

# Regex patterns
MONTH_REGEX = re.compile(r"^\d{4}-\d{2}$")
DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CUTOFF_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Fixed business bounds (ADR-01 & Phase 0 Decision Record)
SUPPORTED_MONTH = "2026-01"
MIN_JANUARY_DATE = date(2026, 1, 1)
MAX_JANUARY_DATE = date(2026, 1, 31)
MAX_QUERY_WINDOW_DAYS = 31
MAX_PAGE_SIZE = 200


def validate_month_safeguard(month: str) -> str:
    """Validate target month format and enforce supported analysis window boundary."""
    cleaned = month.strip()
    if not MONTH_REGEX.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid month format '{month}'. Expected YYYY-MM (e.g. 2026-01).",
        )

    # Enforce pilot window (January 2026)
    if cleaned != SUPPORTED_MONTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported analysis month '{month}'. This decision-support pilot is "
                f"strictly scoped to January 2026 ('{SUPPORTED_MONTH}')."
            ),
        )
    return cleaned


def validate_cutoff_safeguard(cutoff: str) -> str:
    """Validate 24-hour HH:MM format for decision cutoff."""
    cleaned = cutoff.strip()
    match = CUTOFF_REGEX.match(cleaned)
    if not match:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid cutoff time format '{cutoff}'. Expected HH:MM between 00:00 and 23:59 (e.g. 12:00).",
        )
    return cleaned


def validate_date_range_safeguards(
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> tuple[date, date]:
    """Validate start and end dates, enforcing range caps and January 2026 bounds."""
    start_d = MIN_JANUARY_DATE
    end_d = MAX_JANUARY_DATE

    if start_date_str:
        if not DATE_REGEX.match(start_date_str.strip()):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid start_date format '{start_date_str}'. Expected YYYY-MM-DD.",
            )
        try:
            start_d = datetime.strptime(start_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid calendar date '{start_date_str}'.")

    if end_date_str:
        if not DATE_REGEX.match(end_date_str.strip()):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid end_date format '{end_date_str}'. Expected YYYY-MM-DD.",
            )
        try:
            end_d = datetime.strptime(end_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid calendar date '{end_date_str}'.")

    # Constraint checks
    if end_d < start_d:
        raise HTTPException(
            status_code=400,
            detail=f"end_date ({end_d}) cannot be earlier than start_date ({start_d}).",
        )

    if start_d < MIN_JANUARY_DATE or end_d > MAX_JANUARY_DATE:
        raise HTTPException(
            status_code=400,
            detail=f"Date range ({start_d} to {end_d}) must fall entirely within January 2026 (2026-01-01 to 2026-01-31).",
        )

    window_days = (end_d - start_d).days + 1
    if window_days > MAX_QUERY_WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Query range of {window_days} days exceeds maximum allowed limit of {MAX_QUERY_WINDOW_DAYS} days.",
        )

    return start_d, end_d


def validate_pagination_safeguards(page: int, page_size: int) -> tuple[int, int]:
    """Validate pagination parameters, capping page_size to prevent memory exhaustion."""
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail=f"page must be an integer greater than or equal to 1 (received {page}).",
        )
    if not (1 <= page_size <= MAX_PAGE_SIZE):
        raise HTTPException(
            status_code=422,
            detail=f"page_size must be between 1 and {MAX_PAGE_SIZE} (received {page_size}).",
        )
    return page, page_size
