"""Health check route."""

from fastapi import APIRouter

from gregory.api.schemas import HealthResponse
from gregory.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check for Docker and load balancers."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        ollama_configured=bool(settings.ollama_base_url),
    )
