from fastapi import APIRouter, Depends, Request
import httpx

from app.api.deps import get_data_loader
from app.api.routers.overview import get_overview
from app.core.config import Settings, get_settings
from app.schemas.ai import AiBriefingRequest, AiBriefingResponse
from app.services.ai_copilot import AiCopilotService
from app.services.data_loader import DataLoaderService

router = APIRouter(prefix="/api/v1/ai", tags=["ai-copilot"])


@router.post("/briefing", response_model=AiBriefingResponse)
async def generate_ai_briefing(
    payload: AiBriefingRequest,
    raw_request: Request,
    loader: DataLoaderService = Depends(get_data_loader),
    settings: Settings = Depends(get_settings),
) -> AiBriefingResponse:
    """Generate an AI-powered Trading Desk Morning Briefing and thermal procurement recommendations."""
    overview = await get_overview(
        month=payload.month,
        cutoff=payload.cutoff,
        loader=loader,
    )

    # Use the pooled application HTTP client if available, else transient client
    http_client = getattr(raw_request.app.state, "http_client", None)
    if http_client is None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await AiCopilotService.generate_briefing(
                request=payload,
                overview=overview,
                largest_errors=overview.largest_errors,
                http_client=client,
                settings=settings,
            )

    return await AiCopilotService.generate_briefing(
        request=payload,
        overview=overview,
        largest_errors=overview.largest_errors,
        http_client=http_client,
        settings=settings,
    )
