"""Backward-compatibility re-export of health router."""

from app.api.routers.health import HealthResponse, liveness, readiness, router

__all__ = ["router", "liveness", "readiness", "HealthResponse"]
