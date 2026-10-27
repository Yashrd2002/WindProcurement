from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Union

import httpx

from app.core.config import Settings, get_settings
from app.core.http_client import create_http_client
from app.core.retry import execute_with_retry
from app.services.models import ForecastRecord, FuelRecord

logger = logging.getLogger("wind_procurement.elexon")


class ElexonClientError(Exception):
    """Base exception for Elexon client errors."""
    pass


class ElexonUpstreamError(ElexonClientError):
    """Raised when upstream Elexon API fails with 5xx or connection error."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Upstream Elexon error ({status_code}): {message}")


class ElexonValidationError(ElexonClientError):
    """Raised when Elexon rejects query parameters with HTTP 400."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(f"Elexon validation error: {message}")


class ElexonPayloadError(ElexonClientError):
    """Raised when Elexon response payload is malformed or unparseable."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Elexon payload error: {message}")


def format_iso_utc(dt_val: Union[datetime, str]) -> str:
    """Format datetime as strict ISO 8601 UTC string (YYYY-MM-DDTHH:MM:SSZ)."""
    if isinstance(dt_val, str):
        if dt_val.endswith("Z"):
            return dt_val
        try:
            dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return dt_val
    else:
        dt = dt_val

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    """Typed asynchronous HTTP client for the Elexon Insights BMRS streaming API."""

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = http_client or create_http_client(self.settings)

    @staticmethod
    def parse_fuelhh_record(raw: dict[str, Any]) -> Optional[FuelRecord]:
        """Parse a single raw FUELHH dictionary into a typed FuelRecord."""
        try:
            start_time_raw = raw.get("startTime")
            pub_time_raw = raw.get("publishTime")
            if not start_time_raw or not pub_time_raw:
                return None

            start_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            pub_dt = datetime.fromisoformat(pub_time_raw.replace("Z", "+00:00"))

            return FuelRecord(
                dataset="FUELHH",
                publish_time=pub_dt,
                start_time=start_dt,
                settlement_date=str(raw["settlementDate"]),
                settlement_period=int(raw["settlementPeriod"]),
                fuel_type=str(raw["fuelType"]).upper(),
                generation_mw=float(raw["generation"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(f"Skipping malformed FUELHH record: {exc} in {raw}")
            return None

    @staticmethod
    def parse_windfor_record(raw: dict[str, Any]) -> Optional[ForecastRecord]:
        """Parse a single raw WINDFOR dictionary into a typed ForecastRecord."""
        try:
            start_time_raw = raw.get("startTime")
            pub_time_raw = raw.get("publishTime")
            if not start_time_raw or not pub_time_raw:
                return None

            start_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
            pub_dt = datetime.fromisoformat(pub_time_raw.replace("Z", "+00:00"))

            return ForecastRecord(
                dataset="WINDFOR",
                publish_time=pub_dt,
                start_time=start_dt,
                generation_mw=float(raw["generation"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning(f"Skipping malformed WINDFOR record: {exc} in {raw}")
            return None

    def parse_fuelhh_stream(
        self,
        raw_items: List[dict[str, Any]],
        fuel_type: Optional[str] = "WIND",
    ) -> List[FuelRecord]:
        """Parse and filter a stream of raw FUELHH records."""
        records: List[FuelRecord] = []
        target_fuel = fuel_type.upper() if fuel_type else None

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            if target_fuel and str(item.get("fuelType", "")).upper() != target_fuel:
                continue
            parsed = self.parse_fuelhh_record(item)
            if parsed:
                records.append(parsed)

        return records

    def parse_windfor_stream(self, raw_items: List[dict[str, Any]]) -> List[ForecastRecord]:
        """Parse a stream of raw WINDFOR forecast records."""
        records: List[ForecastRecord] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            parsed = self.parse_windfor_record(item)
            if parsed:
                records.append(parsed)
        return records

    async def _get_with_retry(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """Execute GET request with bounded exponential backoff for transient failures."""
        return await execute_with_retry(
            request_callable=lambda: self._client.get(url, params=params),
            max_retries=self.settings.http_max_retries,
            operation_name=f"Elexon {url}",
        )

    async def fetch_fuelhh_stream(
        self,
        publish_from: Union[datetime, str],
        publish_to: Union[datetime, str],
        fuel_type: Optional[str] = "WIND",
    ) -> List[FuelRecord]:
        """Fetch half-hourly fuel generation actuals from Elexon FUELHH/stream."""
        params = {
            "publishDateTimeFrom": format_iso_utc(publish_from),
            "publishDateTimeTo": format_iso_utc(publish_to),
        }
        url = "/datasets/FUELHH/stream"

        try:
            response = await self._get_with_retry(url, params=params)
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error fetching {url}: {exc}")
            raise ElexonUpstreamError(503, f"Unable to reach Elexon BMRS API after retries: {exc}") from exc

        if response.status_code == 400:
            err_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            raise ElexonValidationError("Invalid query parameters sent to Elexon", details=err_data)

        if response.status_code == 429 or response.status_code >= 500:
            raise ElexonUpstreamError(response.status_code, response.text[:200])

        if response.status_code != 200:
            raise ElexonClientError(f"Unexpected response status {response.status_code}: {response.text[:200]}")

        try:
            raw_data = response.json()
        except Exception as exc:
            raise ElexonPayloadError(f"Failed to parse JSON stream from {url}: {exc}") from exc

        if not isinstance(raw_data, list):
            raise ElexonPayloadError(f"Expected list response from stream, received {type(raw_data)}")

        return self.parse_fuelhh_stream(raw_data, fuel_type=fuel_type)

    async def fetch_windfor_stream(
        self,
        publish_from: Union[datetime, str],
        publish_to: Union[datetime, str],
    ) -> List[ForecastRecord]:
        """Fetch wind generation forecasts from Elexon WINDFOR/stream."""
        params = {
            "publishDateTimeFrom": format_iso_utc(publish_from),
            "publishDateTimeTo": format_iso_utc(publish_to),
        }
        url = "/datasets/WINDFOR/stream"

        try:
            response = await self._get_with_retry(url, params=params)
        except httpx.RequestError as exc:
            logger.error(f"HTTP request error fetching {url}: {exc}")
            raise ElexonUpstreamError(503, f"Unable to reach Elexon BMRS API after retries: {exc}") from exc

        if response.status_code == 400:
            err_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            raise ElexonValidationError("Invalid query parameters sent to Elexon", details=err_data)

        if response.status_code == 429 or response.status_code >= 500:
            raise ElexonUpstreamError(response.status_code, response.text[:200])

        if response.status_code != 200:
            raise ElexonClientError(f"Unexpected response status {response.status_code}: {response.text[:200]}")

        try:
            raw_data = response.json()
        except Exception as exc:
            raise ElexonPayloadError(f"Failed to parse JSON stream from {url}: {exc}") from exc

        if not isinstance(raw_data, list):
            raise ElexonPayloadError(f"Expected list response from stream, received {type(raw_data)}")

        return self.parse_windfor_stream(raw_data)

    def load_fixture_fuelhh(self, filepath: Union[str, Path], fuel_type: Optional[str] = "WIND") -> List[FuelRecord]:
        """Load and parse a local FUELHH JSON fixture file for offline testing."""
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Fixture file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        return self.parse_fuelhh_stream(raw_data, fuel_type=fuel_type)

    def load_fixture_windfor(self, filepath: Union[str, Path]) -> List[ForecastRecord]:
        """Load and parse a local WINDFOR JSON fixture file for offline testing."""
        path = Path(filepath)
        if not path.is_file():
            raise FileNotFoundError(f"Fixture file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        return self.parse_windfor_stream(raw_data)
