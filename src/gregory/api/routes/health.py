"""Health check route."""

from fastapi import APIRouter

from gregory.ai.router import get_provider
from gregory.api.schemas import HealthResponse
from gregory.config import get_settings

router = APIRouter(tags=["health"])


def _provider_name() -> str | None:
    """Return the active provider name, or None if none configured."""
    p = get_provider()
    if p is None:
        return None
    return type(p).__name__.replace("Provider", "").lower()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check for Docker and load balancers."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        ollama_configured=bool(settings.ollama_base_url),
        ai_provider=_provider_name(),
    )
