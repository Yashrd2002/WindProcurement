from typing import AsyncGenerator
import httpx
from starlette.requests import Request

from app.core.config import Settings, get_settings


def create_http_client(settings: Settings | None = None) -> httpx.AsyncClient:
    """Create a configured httpx AsyncClient with connection pooling and timeouts."""
    if settings is None:
        settings = get_settings()

    timeout = httpx.Timeout(
        timeout=settings.http_timeout_seconds,
        connect=settings.http_connect_timeout_seconds,
    )
    limits = httpx.Limits(
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.http_max_keepalive,
    )
    headers = {
        "User-Agent": f"{settings.app_name}/0.1.0 (Day-Ahead Analytics)",
        "Accept": "application/json",
    }

    return httpx.AsyncClient(
        base_url=settings.elexon_base_url,
        timeout=timeout,
        limits=limits,
        headers=headers,
        follow_redirects=True,
    )


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """FastAPI dependency to retrieve the application-managed HTTP client."""
    client = getattr(request.app.state, "http_client", None)
    if client is None or client.is_closed:
        # Fallback for direct testing without lifespan
        return create_http_client()
    return client
