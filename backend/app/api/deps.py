from datetime import date
from typing import Optional
from fastapi import Query

from app.core.config import get_settings
from app.core.safeguards import (
    MAX_PAGE_SIZE,
    validate_cutoff_safeguard,
    validate_date_range_safeguards,
    validate_month_safeguard,
    validate_pagination_safeguards,
)

settings = get_settings()


def validate_target_month(
    month: str = Query(
        default=settings.default_target_month,
        description="Target delivery month in YYYY-MM format (e.g. 2026-01)",
        examples=["2026-01"],
    )
) -> str:
    """Validate target month parameter format and bounded scope (P4-06)."""
    return validate_month_safeguard(month)


def validate_cutoff_time(
    cutoff: str = Query(
        default=settings.default_cutoff_time,
        description="Day-ahead decision cutoff time (HH:MM in Europe/London on Day D-1)",
        examples=["12:00", "11:00", "17:00", "23:00"],
    )
) -> str:
    """Validate cutoff time format (24-hour HH:MM)."""
    return validate_cutoff_safeguard(cutoff)


def validate_date_range(
    start_date: Optional[str] = Query(
        default=None,
        description="Optional filter start date YYYY-MM-DD (must fall in January 2026)",
        examples=["2026-01-01"],
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="Optional filter end date YYYY-MM-DD (must fall in January 2026)",
        examples=["2026-01-31"],
    ),
) -> tuple[date, date]:
    """Validate date range window and cap safeguards (P4-06)."""
    return validate_date_range_safeguards(start_date, end_date)


def validate_pagination(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=48, ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})"),
) -> tuple[int, int]:
    """Validate pagination parameters (P4-06)."""
    return validate_pagination_safeguards(page, page_size)


def get_data_loader() -> "DataLoaderService":
    """Dependency provider for DataLoaderService using global TTL cache."""
    from app.core.cache import get_cache
    from app.services.data_loader import DataLoaderService

    return DataLoaderService(
        cache=get_cache(default_ttl=settings.cache_ttl_seconds),
        settings=settings,
    )
