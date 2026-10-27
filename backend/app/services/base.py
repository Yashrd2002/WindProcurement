"""Base service interfaces and common types for Elexon retrieval and analytics."""

from typing import Protocol, Any, Dict


class DataRetrievalService(Protocol):
    """Protocol for upstream Elexon data retrieval and caching."""

    async def get_actuals(self, month: str) -> list[dict[str, Any]]:
        ...

    async def get_forecasts(self, month: str) -> list[dict[str, Any]]:
        ...
