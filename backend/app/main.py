from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers.ai import router as ai_router
from app.api.routers.health import router as health_router
from app.api.routers.intervals import router as intervals_router
from app.api.routers.overview import router as overview_router
from app.api.routers.quality import router as quality_router
from app.api.routers.timeseries import router as timeseries_router
from app.core.config import get_settings
from app.core.http_client import create_http_client
from app.core.logging import RequestLoggingMiddleware, setup_logging
from app.services.elexon_client import ElexonPayloadError, ElexonUpstreamError

settings = get_settings()
setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager managing pooled HTTP client."""
    app.state.http_client = create_http_client(settings)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Decision-support analytics platform for UK wholesale day-ahead wind procurement.",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health_router)
app.include_router(overview_router)
app.include_router(timeseries_router)
app.include_router(intervals_router)
app.include_router(quality_router)
app.include_router(ai_router)
 
 
@app.exception_handler(ElexonUpstreamError)
async def elexon_upstream_error_handler(request: Request, exc: ElexonUpstreamError) -> JSONResponse:
    """Format upstream Elexon API failures into structured JSON responses (P7-04 / ADR-05)."""
    status_code = exc.status_code if 500 <= exc.status_code <= 504 else 502
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": f"Upstream Elexon service condition: {exc.message}",
            "status_code": exc.status_code,
            "error_type": "upstream_service_error",
        },
    )


@app.exception_handler(ElexonPayloadError)
async def elexon_payload_error_handler(request: Request, exc: ElexonPayloadError) -> JSONResponse:
    """Format malformed upstream payload into structured 502 Bad Gateway response."""
    return JSONResponse(
        status_code=502,
        content={
            "detail": f"Upstream Elexon payload malformed: {exc.message}",
            "status_code": 502,
            "error_type": "upstream_payload_error",
        },
    )

# Production static assets mount
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
