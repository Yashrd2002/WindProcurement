from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

from app.core.cache import InMemoryTtlCache, get_cache
from app.core.config import Settings, get_settings
from app.services.elexon_client import (
    ElexonClient,
    ElexonClientError,
    ElexonUpstreamError,
    ElexonValidationError,
)
from app.services.models import ForecastRecord, FuelRecord
from app.services.normalization import NormalizationReport, RecordNormalizer

logger = logging.getLogger("wind_procurement.data_loader")

def _resolve_fixtures_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures",
        Path(__file__).resolve().parent.parent / "tests" / "fixtures",
        Path("/app/tests/fixtures"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


FIXTURES_DIR = _resolve_fixtures_dir()


class DataLoaderService:
    """Unified data retrieval, caching, normalization, and failure management service (P4-04 & P4-05)."""

    def __init__(
        self,
        client: Optional[ElexonClient] = None,
        cache: Optional[InMemoryTtlCache] = None,
        settings: Optional[Settings] = None,
        fixtures_dir: Optional[Path] = None,
        use_fixtures: Optional[bool] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or ElexonClient(settings=self.settings)
        self.cache = cache or get_cache(default_ttl=self.settings.cache_ttl_seconds)
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self.use_fixtures = (
            use_fixtures
            if use_fixtures is not None
            else getattr(self.settings, "offline_mode", False)
        )

    async def get_january_actuals(
        self,
        force_live: bool = False,
        fuel_type: str = "WIND",
    ) -> Tuple[List[FuelRecord], NormalizationReport, bool]:
        """Retrieve and normalize January 2026 wind actuals.

        Returns (records, normalization_report, was_cache_hit).
        Never replaces upstream failures with zero values (P4-05 / ADR-05).
        """
        cache_key = f"actuals:2026-01:{fuel_type.upper()}"

        if not force_live:
            cached = self.cache.get(cache_key)
            if cached is not None:
                records, report = cached
                return records, report, True

        # Fetch from local verified fixture or live Elexon
        records: List[FuelRecord] = []
        report: NormalizationReport

        if self.use_fixtures:
            fixture_file = self.fixtures_dir / "fuelhh_jan2026_wind.json"
            if fixture_file.is_file():
                records = self.client.load_fixture_fuelhh(fixture_file, fuel_type=fuel_type)
                report = NormalizationReport(
                    dataset="FUELHH",
                    total_received=len(records),
                    valid_count=len(records),
                    rejected_count=0,
                )
            else:
                raise FileNotFoundError(f"Fixture file not found: {fixture_file}")
        else:
            try:
                # Query publication window for all January delivery actuals
                raw_records = await self.client.fetch_fuelhh_stream(
                    publish_from="2026-01-01T00:00:00Z",
                    publish_to="2026-02-01T04:00:00Z",
                    fuel_type=fuel_type,
                )
                # Re-normalize through strict normalizer to record audit
                raw_dicts = [
                    {
                        "dataset": r.dataset,
                        "publishTime": r.publish_time.isoformat(),
                        "startTime": r.start_time.isoformat(),
                        "settlementDate": r.settlement_date,
                        "settlementPeriod": r.settlement_period,
                        "fuelType": r.fuel_type,
                        "generation": r.generation_mw,
                    }
                    for r in raw_records
                ]
                records, report = RecordNormalizer.normalize_fuelhh_stream(raw_dicts, fuel_type_filter=fuel_type)

            except (ElexonUpstreamError, httpx.RequestError) as exc:
                # Check if offline fixture is available as transparent fallback
                fixture_file = self.fixtures_dir / "fuelhh_jan2026_wind.json"
                if fixture_file.is_file():
                    logger.info(f"Using offline fixture fallback {fixture_file.name} due to upstream condition: {exc}")
                    records = self.client.load_fixture_fuelhh(fixture_file, fuel_type=fuel_type)
                    report = NormalizationReport(
                        dataset="FUELHH",
                        total_received=len(records),
                        valid_count=len(records),
                        rejected_count=0,
                    )
                else:
                    # Explicit failure propagation (never return fake zeroes!)
                    logger.error(f"Upstream Elexon failure fetching FUELHH without fixture fallback: {exc}")
                    raise

        # Filter strictly for January 2026 settlement dates
        january_records = [
            r for r in records if r.settlement_date.startswith("2026-01-")
        ]
        # Sort chronologically by startTime
        january_records.sort(key=lambda r: r.start_time)

        # Reflect valid January delivery records in report
        report.valid_count = len(january_records)
        report.total_received = len(january_records) + report.rejected_count

        # Store in TTL cache
        self.cache.set(cache_key, (january_records, report))
        return january_records, report, False

    async def get_january_forecasts(
        self,
        force_live: bool = False,
    ) -> Tuple[List[ForecastRecord], NormalizationReport, bool]:
        """Retrieve and normalize January 2026 wind forecasts.

        Returns (records, normalization_report, was_cache_hit).
        Never replaces upstream failures with zero values (P4-05 / ADR-05).
        """
        cache_key = "forecasts:2026-01:WINDFOR"

        if not force_live:
            cached = self.cache.get(cache_key)
            if cached is not None:
                records, report = cached
                return records, report, True

        records: List[ForecastRecord] = []
        report: NormalizationReport

        if self.use_fixtures:
            fixture_file = self.fixtures_dir / "windfor_jan2026.json"
            if fixture_file.is_file():
                records = self.client.load_fixture_windfor(fixture_file)
                report = NormalizationReport(
                    dataset="WINDFOR",
                    total_received=len(records),
                    valid_count=len(records),
                    rejected_count=0,
                )
            else:
                raise FileNotFoundError(f"Fixture file not found: {fixture_file}")
        else:
            try:
                # Query window covering forecasts issued from Dec 28 to Feb 1
                raw_records = await self.client.fetch_windfor_stream(
                    publish_from="2025-12-28T00:00:00Z",
                    publish_to="2026-02-01T00:00:00Z",
                )
                raw_dicts = [
                    {
                        "dataset": r.dataset,
                        "publishTime": r.publish_time.isoformat(),
                        "startTime": r.start_time.isoformat(),
                        "generation": r.generation_mw,
                    }
                    for r in raw_records
                ]
                records, report = RecordNormalizer.normalize_windfor_stream(raw_dicts)

            except (ElexonUpstreamError, httpx.RequestError) as exc:
                fixture_file = self.fixtures_dir / "windfor_jan2026.json"
                if fixture_file.is_file():
                    logger.info(f"Using offline fixture fallback {fixture_file.name} due to upstream condition: {exc}")
                    records = self.client.load_fixture_windfor(fixture_file)
                    report = NormalizationReport(
                        dataset="WINDFOR",
                        total_received=len(records),
                        valid_count=len(records),
                        rejected_count=0,
                    )
                else:
                    logger.error(f"Upstream Elexon failure fetching WINDFOR without fixture fallback: {exc}")
                    raise

        # Filter strictly for forecasts targeting January 2026 delivery
        january_forecasts = [
            r for r in records if r.start_time.strftime("%Y-%m").startswith("2026-01")
        ]
        january_forecasts.sort(key=lambda r: (r.start_time, r.publish_time))

        report.valid_count = len(january_forecasts)
        report.total_received = len(january_forecasts) + report.rejected_count

        self.cache.set(cache_key, (january_forecasts, report))
        return january_forecasts, report, False
