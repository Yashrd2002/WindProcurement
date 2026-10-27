from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get("/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Report process liveness without calling external upstream dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
def readiness() -> HealthResponse:
    """Report readiness to serve incoming traffic."""
    return HealthResponse(status="ok")
