"""Health check route."""

from fastapi import APIRouter

from gregory.ai.config import resolve_providers_ordered
from gregory.ai.router import get_provider
from gregory.api.schemas import HealthResponse

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
    return HealthResponse(
        status="ok",
        ollama_configured=any(
            r.provider_type == "ollama" for r in resolve_providers_ordered()
        ),
        ai_provider=_provider_name(),
    )
