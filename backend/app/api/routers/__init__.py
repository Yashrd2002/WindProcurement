from app.api.routers.ai import router as ai_router
from app.api.routers.health import router as health_router
from app.api.routers.intervals import router as intervals_router
from app.api.routers.overview import router as overview_router
from app.api.routers.quality import router as quality_router
from app.api.routers.timeseries import router as timeseries_router

__all__ = [
    "ai_router",
    "health_router",
    "intervals_router",
    "overview_router",
    "quality_router",
    "timeseries_router",
]
