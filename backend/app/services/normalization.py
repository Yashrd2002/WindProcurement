from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re
from typing import Any, List, Optional, Tuple

from app.services.models import ForecastRecord, FuelRecord

logger = logging.getLogger("wind_procurement.normalization")

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class NormalizationReport:
    """Audit report of raw record ingestion and rejection reasons."""

    dataset: str
    total_received: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    rejection_reasons: List[str] = field(default_factory=list)


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


class RecordNormalizer:
    """Normalizes raw Elexon payloads into strictly validated domain entities (P4-04)."""

    @classmethod
    def normalize_fuelhh_record(cls, raw: dict[str, Any]) -> Tuple[Optional[FuelRecord], Optional[str]]:
        """Normalize a single FUELHH dictionary, returning (record, rejection_reason)."""
        if not isinstance(raw, dict):
            return None, "Item is not a dictionary"

        # 1. Required fields presence check
        required_keys = ["startTime", "publishTime", "settlementDate", "settlementPeriod", "fuelType", "generation"]
        missing_keys = [k for k in required_keys if k not in raw or raw[k] is None]
        if missing_keys:
            return None, f"Missing required fields: {', '.join(missing_keys)}"

        # 2. Timestamp validation
        start_dt = parse_iso_datetime(raw["startTime"])
        if not start_dt:
            return None, f"Invalid startTime ISO format: {raw.get('startTime')}"

        pub_dt = parse_iso_datetime(raw["publishTime"])
        if not pub_dt:
            return None, f"Invalid publishTime ISO format: {raw.get('publishTime')}"

        # 3. Settlement date validation
        settlement_date = str(raw["settlementDate"]).strip()
        if not DATE_REGEX.match(settlement_date):
            return None, f"Invalid settlementDate format: {settlement_date}"

        # 4. Settlement period index validation (1 to 50)
        try:
            period = int(raw["settlementPeriod"])
            if not (1 <= period <= 50):
                return None, f"settlementPeriod {period} out of valid range (1-50)"
        except (ValueError, TypeError):
            return None, f"Non-integer settlementPeriod: {raw.get('settlementPeriod')}"

        # 5. Generation value validation (must be non-negative number)
        try:
            gen_val = float(raw["generation"])
            if gen_val < 0.0:
                return None, f"Negative generation value: {gen_val} MW"
        except (ValueError, TypeError):
            return None, f"Non-numeric generation value: {raw.get('generation')}"

        fuel_type = str(raw["fuelType"]).strip().upper()
        if not fuel_type:
            return None, "Empty fuelType string"

        return FuelRecord(
            dataset="FUELHH",
            publish_time=pub_dt,
            start_time=start_dt,
            settlement_date=settlement_date,
            settlement_period=period,
            fuel_type=fuel_type,
            generation_mw=gen_val,
        ), None

    @classmethod
    def normalize_windfor_record(cls, raw: dict[str, Any]) -> Tuple[Optional[ForecastRecord], Optional[str]]:
        """Normalize a single WINDFOR dictionary, returning (record, rejection_reason)."""
        if not isinstance(raw, dict):
            return None, "Item is not a dictionary"

        required_keys = ["startTime", "publishTime", "generation"]
        missing_keys = [k for k in required_keys if k not in raw or raw[k] is None]
        if missing_keys:
            return None, f"Missing required fields: {', '.join(missing_keys)}"

        start_dt = parse_iso_datetime(raw["startTime"])
        if not start_dt:
            return None, f"Invalid startTime ISO format: {raw.get('startTime')}"

        pub_dt = parse_iso_datetime(raw["publishTime"])
        if not pub_dt:
            return None, f"Invalid publishTime ISO format: {raw.get('publishTime')}"

        try:
            gen_val = float(raw["generation"])
            if gen_val < 0.0:
                return None, f"Negative generation value: {gen_val} MW"
        except (ValueError, TypeError):
            return None, f"Non-numeric generation value: {raw.get('generation')}"

        return ForecastRecord(
            dataset="WINDFOR",
            publish_time=pub_dt,
            start_time=start_dt,
            generation_mw=gen_val,
        ), None

    @classmethod
    def normalize_fuelhh_stream(
        cls,
        raw_items: List[dict[str, Any]],
        fuel_type_filter: Optional[str] = "WIND",
    ) -> Tuple[List[FuelRecord], NormalizationReport]:
        """Normalize an entire list of raw FUELHH records with an audit report."""
        report = NormalizationReport(dataset="FUELHH", total_received=len(raw_items))
        records: List[FuelRecord] = []
        target_fuel = fuel_type_filter.upper() if fuel_type_filter else None

        for item in raw_items:
            record, rejection = cls.normalize_fuelhh_record(item)
            if record:
                if target_fuel and record.fuel_type != target_fuel:
                    continue
                records.append(record)
                report.valid_count += 1
            else:
                report.rejected_count += 1
                if rejection and rejection not in report.rejection_reasons:
                    report.rejection_reasons.append(rejection)

        return records, report

    @classmethod
    def normalize_windfor_stream(
        cls,
        raw_items: List[dict[str, Any]],
    ) -> Tuple[List[ForecastRecord], NormalizationReport]:
        """Normalize an entire list of raw WINDFOR forecast records with an audit report."""
        report = NormalizationReport(dataset="WINDFOR", total_received=len(raw_items))
        records: List[ForecastRecord] = []

        for item in raw_items:
            record, rejection = cls.normalize_windfor_record(item)
            if record:
                records.append(record)
                report.valid_count += 1
            else:
                report.rejected_count += 1
                if rejection and rejection not in report.rejection_reasons:
                    report.rejection_reasons.append(rejection)

        return records, report
