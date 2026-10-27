"""Services package for Elexon ingestion, validation, normalization, and analytics."""

from app.services.base import DataRetrievalService
from app.services.data_loader import DataLoaderService
from app.services.elexon_client import (
    ElexonClient,
    ElexonClientError,
    ElexonPayloadError,
    ElexonUpstreamError,
    ElexonValidationError,
    format_iso_utc,
)
from app.services.analytics import (
    AnalyticsEngine,
    CoverageAudit,
    ForecastMetrics,
    compute_bias,
    compute_day_ahead_cutoff_utc,
    compute_mae,
    compute_potential_shortfall,
    compute_rmse,
    compute_wape,
    select_operational_forecast,
)
from app.services.models import AlignedInterval, ForecastRecord, FuelRecord
from app.services.normalization import NormalizationReport, RecordNormalizer

__all__ = [
    "DataRetrievalService",
    "DataLoaderService",
    "ElexonClient",
    "ElexonClientError",
    "ElexonUpstreamError",
    "ElexonValidationError",
    "ElexonPayloadError",
    "FuelRecord",
    "ForecastRecord",
    "AlignedInterval",
    "RecordNormalizer",
    "NormalizationReport",
    "AnalyticsEngine",
    "ForecastMetrics",
    "CoverageAudit",
    "compute_mae",
    "compute_rmse",
    "compute_bias",
    "compute_wape",
    "compute_potential_shortfall",
    "compute_day_ahead_cutoff_utc",
    "select_operational_forecast",
    "format_iso_utc",
]
