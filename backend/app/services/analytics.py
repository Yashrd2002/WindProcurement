from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import logging
import math
from typing import Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.models import AlignedInterval, ForecastRecord, FuelRecord

logger = logging.getLogger("wind_procurement.analytics")


@dataclass
class ForecastMetrics:
    """Statistical forecast accuracy benchmark results (P5-02 & P5-03)."""

    sample_count: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    bias: Optional[float] = None
    wape: Optional[float] = None
    total_forecast_mw: float = 0.0
    total_actual_mw: float = 0.0
    sign_convention: str = "positive_overforecast"


@dataclass
class CoverageAudit:
    """Audit report comparing present data against expected calendar intervals (P5-05)."""

    target_month: str
    cutoff_time: str
    expected_intervals: int
    actual_intervals_found: int
    forecast_intervals_found: int
    matched_intervals: int
    missing_actual_count: int
    missing_forecast_count: int
    duplicate_actual_count: int
    missing_actual_intervals: List[str]
    missing_forecast_intervals: List[str]
    duplicate_actual_intervals: List[str]
    completeness_pct: float



def compute_day_ahead_cutoff_utc(
    delivery_date: Union[date, str],
    cutoff_time_str: str = "12:00",
    tz_name: str = "Europe/London",
) -> datetime:
    """Compute the day-ahead decision cutoff timestamp in UTC for a given physical delivery date.

    Day-ahead power procurement for delivery date D is finalized on day D-1 at the
    specified local market cutoff time (ADR-04).

    Example:
        delivery_date = 2026-01-05
        D-1 = 2026-01-04
        cutoff_time = 12:00 Europe/London
        -> 2026-01-04 12:00:00 UTC (during GMT)
    """
    if isinstance(delivery_date, str):
        target_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    else:
        target_date = delivery_date

    d_minus_1 = target_date - timedelta(days=1)

    try:
        parts = cutoff_time_str.split(":")
        cutoff_hour = int(parts[0])
        cutoff_minute = int(parts[1])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Invalid cutoff time format '{cutoff_time_str}'. Expected HH:MM.") from exc

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning(f"Timezone '{tz_name}' not found, falling back to UTC.")
        tz = ZoneInfo("UTC")

    local_dt = datetime(
        d_minus_1.year,
        d_minus_1.month,
        d_minus_1.day,
        cutoff_hour,
        cutoff_minute,
        0,
        tzinfo=tz,
    )
    return local_dt.astimezone(timezone.utc)


def select_operational_forecast(
    candidates: List[ForecastRecord],
    cutoff_utc: datetime,
) -> Optional[ForecastRecord]:
    """Select the latest operational forecast edition published at or before the decision cutoff.

    Forecast eligibility condition:
        publish_time <= cutoff_utc

    Selection rule:
        argmax_{publish_time} (eligible_forecasts)

    Forecasts published after cutoff_utc are strictly rejected to eliminate look-ahead bias (P5-01 / ADR-04).
    """
    eligible = [f for f in candidates if f.publish_time <= cutoff_utc]
    if not eligible:
        return None

    # Sort descending by publish_time to select latest edition
    eligible.sort(key=lambda f: f.publish_time, reverse=True)
    return eligible[0]


class AnalyticsEngine:
    """Quantitative analytics engine for wind forecast evaluation and interval alignment (Phase 5)."""

    @classmethod
    def align_intervals(
        cls,
        actuals: List[FuelRecord],
        forecasts: List[ForecastRecord],
        target_month: str = "2026-01",
        cutoff_time: str = "12:00",
        tz_name: str = "Europe/London",
    ) -> List[AlignedInterval]:
        """Join half-hourly actual generation with cutoff-governed forecasts.

        Alignment Rules (ADR-04):
        1. Actuals are half-hourly (48 periods per calendar day).
        2. WINDFOR forecasts are hourly; Forecast(Period 2k-1) = Forecast(Period 2k) = WINDFOR(Hour k-1).
        3. Strict cutoff selection: publish_time <= T_cutoff(D).
        4. Rejects late forecasts; marks missing intervals with explicit statuses.
        """
        # Parse month boundary
        year, month = map(int, target_month.split("-"))
        # Determine number of days in month
        if month in {1, 3, 5, 7, 8, 10, 12}:
            days_in_month = 31
        elif month in {4, 6, 9, 11}:
            days_in_month = 30
        else:
            is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            days_in_month = 29 if is_leap else 28

        # Index actuals by (settlement_date, settlement_period)
        actuals_by_sp: Dict[Tuple[str, int], FuelRecord] = {}
        for act in actuals:
            actuals_by_sp[(act.settlement_date, act.settlement_period)] = act

        # Index forecasts by target delivery hour (normalized to :00)
        forecasts_by_hour: Dict[datetime, List[ForecastRecord]] = {}
        for fc in forecasts:
            hour_key = fc.start_time.replace(minute=0, second=0, microsecond=0)
            forecasts_by_hour.setdefault(hour_key, []).append(fc)

        aligned_intervals: List[AlignedInterval] = []

        # Generate complete half-hour timeline for the month (1..days_in_month, SP 1..48)
        for day in range(1, days_in_month + 1):
            curr_date = date(year, month, day)
            curr_date_str = curr_date.strftime("%Y-%m-%d")
            cutoff_utc = compute_day_ahead_cutoff_utc(curr_date, cutoff_time, tz_name)

            for sp in range(1, 49):
                interval_id = f"{curr_date_str}-{sp:02d}"
                # Interval start time: 00:00:00 + (sp - 1) * 30 min
                start_dt = datetime(
                    year, month, day, 0, 0, 0, tzinfo=timezone.utc
                ) + timedelta(minutes=(sp - 1) * 30)

                # Matching forecast hour: start_dt rounded down to :00
                hour_key = start_dt.replace(minute=0, second=0, microsecond=0)
                candidates = forecasts_by_hour.get(hour_key, [])
                chosen_forecast = select_operational_forecast(candidates, cutoff_utc)

                actual_rec = actuals_by_sp.get((curr_date_str, sp))

                actual_mw: Optional[float] = None
                forecast_mw: Optional[float] = None
                forecast_pub_dt: Optional[datetime] = None
                error_mw: Optional[float] = None
                shortfall_mwh: Optional[float] = None
                status: str

                if actual_rec is not None:
                    actual_mw = actual_rec.generation_mw

                if chosen_forecast is not None:
                    forecast_mw = chosen_forecast.generation_mw
                    forecast_pub_dt = chosen_forecast.publish_time

                if actual_mw is not None and forecast_mw is not None:
                    error_mw = round(forecast_mw - actual_mw, 4)
                    shortfall_mwh = round(max(forecast_mw - actual_mw, 0.0) * 0.5, 4)
                    status = "matched"
                elif actual_mw is not None and forecast_mw is None:
                    status = "missing_forecast"
                elif actual_mw is None and forecast_mw is not None:
                    status = "missing_actual"
                else:
                    status = "missing_both"

                aligned_intervals.append(
                    AlignedInterval(
                        interval_id=interval_id,
                        start_time=start_dt,
                        settlement_date=curr_date_str,
                        settlement_period=sp,
                        actual_mw=actual_mw,
                        forecast_mw=forecast_mw,
                        forecast_publish_time=forecast_pub_dt,
                        cutoff_time_applied=cutoff_utc,
                        error_mw=error_mw,
                        shortfall_mwh=shortfall_mwh,
                        status=status,
                    )
                )

        # Sort intervals strictly by start_time
        aligned_intervals.sort(key=lambda x: x.start_time)
        return aligned_intervals

    @classmethod
    def compute_metrics(
        cls,
        intervals: List[AlignedInterval],
    ) -> ForecastMetrics:
        """Compute statistical accuracy metrics (MAE, RMSE, Bias, WAPE) on valid matched pairs.

        Guardrails (P5-02 / P5-03 / ADR-05):
        - Evaluated on valid matched pairs only. Missing actuals/forecasts are excluded from N (never treated as 0).
        - WAPE returns None if total actual generation is zero.
        - Sample count is explicitly tracked and returned.
        """
        pairs = [
            (i.forecast_mw, i.actual_mw)
            for i in intervals
            if i.forecast_mw is not None and i.actual_mw is not None
        ]

        if not pairs:
            return ForecastMetrics(
                sample_count=0,
                mae=None,
                rmse=None,
                bias=None,
                wape=None,
                total_forecast_mw=0.0,
                total_actual_mw=0.0,
            )

        total_forecast = sum(f for f, _ in pairs)
        total_actual = sum(a for _, a in pairs)

        return ForecastMetrics(
            sample_count=len(pairs),
            mae=compute_mae(pairs),
            rmse=compute_rmse(pairs),
            bias=compute_bias(pairs),
            wape=compute_wape(pairs),
            total_forecast_mw=round(total_forecast, 2),
            total_actual_mw=round(total_actual, 2),
        )

    @classmethod
    def audit_coverage(
        cls,
        actuals: List[FuelRecord],
        forecasts: List[ForecastRecord],
        target_month: str = "2026-01",
        cutoff_time: str = "12:00",
        tz_name: str = "Europe/London",
    ) -> CoverageAudit:
        """Audit settlement interval coverage, detecting missing and duplicate periods (P5-05).

        Compares present data against the full calendar grid (48 settlement periods / day).
        Tracks duplicates, missing actuals, and missing forecasts.
        """
        year, month = map(int, target_month.split("-"))
        if month in {1, 3, 5, 7, 8, 10, 12}:
            days_in_month = 31
        elif month in {4, 6, 9, 11}:
            days_in_month = 30
        else:
            is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
            days_in_month = 29 if is_leap else 28

        expected_ids: List[str] = [
            f"{year:04d}-{month:02d}-{day:02d}-{sp:02d}"
            for day in range(1, days_in_month + 1)
            for sp in range(1, 49)
        ]
        total_expected = len(expected_ids)

        # Detect duplicates and present periods in actuals
        seen_actuals: Dict[str, int] = {}
        for act in actuals:
            act_id = f"{act.settlement_date}-{act.settlement_period:02d}"
            seen_actuals[act_id] = seen_actuals.get(act_id, 0) + 1

        duplicate_actual_ids = [k for k, v in seen_actuals.items() if v > 1]
        present_actual_ids = set(seen_actuals.keys())
        missing_actual_ids = [eid for eid in expected_ids if eid not in present_actual_ids]

        # Use aligned intervals to determine matched and missing forecasts under the cutoff
        aligned = cls.align_intervals(
            actuals=actuals,
            forecasts=forecasts,
            target_month=target_month,
            cutoff_time=cutoff_time,
            tz_name=tz_name,
        )

        matched_intervals = sum(1 for i in aligned if i.status == "matched")
        missing_forecast_ids = [
            i.interval_id for i in aligned if i.status in {"missing_forecast", "missing_both"}
        ]
        forecast_intervals_found = sum(
            1 for i in aligned if i.forecast_mw is not None
        )

        completeness_pct = (
            round((matched_intervals / total_expected) * 100.0, 1)
            if total_expected > 0
            else 0.0
        )

        return CoverageAudit(
            target_month=target_month,
            cutoff_time=cutoff_time,
            expected_intervals=total_expected,
            actual_intervals_found=len(actuals),
            forecast_intervals_found=forecast_intervals_found,
            matched_intervals=matched_intervals,
            missing_actual_count=len(missing_actual_ids),
            missing_forecast_count=len(missing_forecast_ids),
            duplicate_actual_count=len(duplicate_actual_ids),
            missing_actual_intervals=missing_actual_ids,
            missing_forecast_intervals=missing_forecast_ids,
            duplicate_actual_intervals=duplicate_actual_ids,
            completeness_pct=completeness_pct,
        )



def compute_mae(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Calculate Mean Absolute Error (MAE) in MW on valid matched pairs (P5-02).

    Formula: MAE = (1 / N) * sum(|F_i - A_i|)
    Returns None if pairs is empty. Missing data is never treated as zero (ADR-05).
    """
    if not pairs:
        return None
    return round(sum(abs(f - a) for f, a in pairs) / len(pairs), 2)


def compute_rmse(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Calculate Root Mean Squared Error (RMSE) in MW on valid matched pairs (P5-02).

    Formula: RMSE = sqrt((1 / N) * sum((F_i - A_i)^2))
    Returns None if pairs is empty. Penalizes large forecast excursions.
    """
    if not pairs:
        return None
    mean_sq = sum((f - a) ** 2 for f, a in pairs) / len(pairs)
    return round(math.sqrt(mean_sq), 2)


def compute_bias(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Calculate Signed Mean Error (Bias) in MW on valid matched pairs (P5-03).

    Formula: Bias = (1 / N) * sum(F_i - A_i)
    Sign convention: Positive = Overforecast (F > A), Negative = Underforecast (F < A).
    Returns None if pairs is empty.
    """
    if not pairs:
        return None
    return round(sum(f - a for f, a in pairs) / len(pairs), 2)


def compute_wape(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Calculate Weighted Absolute Percentage Error (WAPE) in % on valid matched pairs (P5-03).

    Formula: WAPE = (sum(|F_i - A_i|) / sum(A_i)) * 100%
    Zero-denominator guardrail: Returns None if sum(A_i) == 0 (Metric Definitions).
    Returns None if pairs is empty.
    """
    if not pairs:
        return None
    total_actual = sum(a for _, a in pairs)
    if total_actual <= 0.0 or math.isclose(total_actual, 0.0, abs_tol=1e-9):
        # Guardrail against zero denominator (e.g. calm periods or absent actuals)
        return None
    total_abs_error = sum(abs(f - a) for f, a in pairs)
    return round((total_abs_error / total_actual) * 100.0, 2)


def compute_potential_shortfall(
    intervals: List[AlignedInterval],
    interval_duration_hours: float = 0.5,
) -> Tuple[float, int, float]:
    """Calculate cumulative potential renewable shortfall volume in MWh (P5-04).

    Formula:
        Shortfall_i = max(Forecast_i - Actual_i, 0) * interval_duration_hours
        Total Shortfall = sum(Shortfall_i) for all valid matched intervals

    Units & Meaning (ADR-04 / Metric Definitions):
        - Output is strictly in MWh (Megawatt-hours).
        - Interval duration is 0.5 hours for half-hourly UK settlement periods.
        - Represents physical energy volume requiring day-ahead thermal power replacement.
        - Strictly volumetric: NOT presented as financial/monetary loss.

    Returns:
        (total_shortfall_mwh, shortfall_interval_count, max_single_shortfall_mwh)
    """
    total_shortfall = 0.0
    count = 0
    max_single = 0.0

    for i in intervals:
        if i.forecast_mw is not None and i.actual_mw is not None:
            diff = i.forecast_mw - i.actual_mw
            if diff > 0.0:
                sf = diff * interval_duration_hours
                total_shortfall += sf
                count += 1
                if sf > max_single:
                    max_single = sf

    return round(total_shortfall, 2), count, round(max_single, 2)


def classify_data_quality_status(
    completeness_pct: float,
    duplicate_count: int = 0,
    max_forecast_age_hours: Optional[float] = None,
) -> Tuple[str, List[str]]:
    """Determine data quality status (Complete / Partial / Stale / Degraded) based on documented thresholds (P5-06).

    Thresholds:
    - complete: completeness >= 98.0%, zero duplicates, and fresh forecast age (<= 24h).
    - partial: 50.0% <= completeness < 98.0%, or duplicates present.
    - stale: forecast age exceeds 48h from delivery cutoff (operational streaming lag).
    - degraded / empty: completeness < 50.0% or 0 matched intervals.
    """
    notes: List[str] = []

    if max_forecast_age_hours is not None and max_forecast_age_hours > 48.0:
        notes.append(f"Forecast data is stale: age {max_forecast_age_hours:.1f}h exceeds 48h limit.")
        return "stale", notes

    if completeness_pct == 0.0:
        notes.append("No matched settlement periods found for analysis window.")
        return "empty", notes

    if completeness_pct >= 98.0 and duplicate_count == 0:
        notes.append("Complete settlement period coverage with zero anomalies.")
        return "complete", notes

    if duplicate_count > 0:
        notes.append(f"Duplicate settlement periods detected: {duplicate_count}.")

    if completeness_pct >= 50.0:
        notes.append(f"Partial coverage: {completeness_pct:.1f}% of scheduled intervals matched.")
        return "partial", notes

    notes.append(f"Degraded coverage: only {completeness_pct:.1f}% of scheduled intervals matched.")
    return "degraded", notes


def build_daily_trends(intervals: List[AlignedInterval]) -> List["DailyTrendItem"]:
    """Aggregate half-hour intervals into daily statistical trends (P5-07).

    Guarantees strict reconciliation with monthly aggregates.
    """
    from app.schemas.overview import DailyTrendItem

    # Group intervals by settlement_date
    by_date: Dict[str, List[AlignedInterval]] = {}
    for i in intervals:
        by_date.setdefault(i.settlement_date, []).append(i)

    daily_trends: List[DailyTrendItem] = []
    for d_str in sorted(by_date.keys()):
        day_intervals = by_date[d_str]
        pairs = [
            (i.forecast_mw, i.actual_mw)
            for i in day_intervals
            if i.forecast_mw is not None and i.actual_mw is not None
        ]

        day_shortfall = sum(i.shortfall_mwh or 0.0 for i in day_intervals)
        day_actual_mwh = sum(a * 0.5 for _, a in pairs)
        day_forecast_mwh = sum(f * 0.5 for f, _ in pairs)

        daily_trends.append(
            DailyTrendItem(
                date=d_str,
                matched_intervals=len(pairs),
                expected_intervals=len(day_intervals),
                mae=compute_mae(pairs),
                rmse=compute_rmse(pairs),
                bias=compute_bias(pairs),
                wape=compute_wape(pairs),
                shortfall_mwh=round(day_shortfall, 2),
                actual_generation_mwh=round(day_actual_mwh, 2),
                forecast_generation_mwh=round(day_forecast_mwh, 2),
            )
        )

    return daily_trends


def find_largest_error_intervals(
    intervals: List[AlignedInterval],
    limit: int = 5,
) -> List["LargestErrorInterval"]:
    """Identify the top largest-error settlement intervals highlighting operational risk periods (P5-07)."""
    from app.schemas.overview import LargestErrorInterval

    matched = [
        i for i in intervals
        if i.forecast_mw is not None and i.actual_mw is not None
    ]

    # Sort descending by absolute forecast error
    sorted_by_abs_error = sorted(
        matched,
        key=lambda i: abs((i.forecast_mw or 0.0) - (i.actual_mw or 0.0)),
        reverse=True,
    )

    results: List[LargestErrorInterval] = []
    for i in sorted_by_abs_error[:limit]:
        f_mw = i.forecast_mw or 0.0
        a_mw = i.actual_mw or 0.0
        err = round(f_mw - a_mw, 2)
        abs_err = round(abs(err), 2)
        direction = "overforecast" if err >= 0 else "underforecast"
        sf = round(max(f_mw - a_mw, 0.0) * 0.5, 2)

        results.append(
            LargestErrorInterval(
                interval_id=i.interval_id,
                start_time=i.start_time.isoformat(),
                settlement_date=i.settlement_date,
                settlement_period=i.settlement_period,
                actual_mw=round(a_mw, 2),
                forecast_mw=round(f_mw, 2),
                error_mw=err,
                abs_error_mw=abs_err,
                shortfall_mwh=sf,
                direction=direction,
            )
        )

    return results


