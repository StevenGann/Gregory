"""AI provider router - selects provider based on config."""

import logging

from gregory.ai.config import ResolvedProvider, resolve_providers_ordered

logger = logging.getLogger(__name__)
from gregory.ai.providers.base import AIProvider
from gregory.ai.providers.claude import ClaudeProvider
from gregory.ai.providers.gemini import GeminiProvider
from gregory.ai.providers.ollama import OllamaProvider
from gregory.config import get_settings


def _instantiate(r: ResolvedProvider) -> AIProvider | None:
    """Create AIProvider from ResolvedProvider."""
    if r.provider_type == "ollama" and r.base_url:
        return OllamaProvider(base_url=r.base_url, model=r.model)
    if r.provider_type == "anthropic" and r.api_key:
        return ClaudeProvider(api_key=r.api_key, model=r.model)
    if r.provider_type == "gemini" and r.api_key:
        return GeminiProvider(api_key=r.api_key, model=r.model)
    return None


def get_provider() -> AIProvider | None:
    """Get the primary configured AI provider. Used for health check and single-provider logic."""
    providers = get_providers_ordered()
    return providers[0][1] if providers else None


def get_providers_ordered() -> list[tuple[str, AIProvider]]:
    """Get all configured providers in fallback order. Primary first, then alternatives on failure."""
    return _providers_from_resolved(resolve_providers_ordered())


def _providers_from_resolved(resolved: list[ResolvedProvider]) -> list[tuple[str, AIProvider]]:
    """Convert resolved providers to (name, provider) list."""
    result: list[tuple[str, AIProvider]] = []
    for r in resolved:
        p = _instantiate(r)
        if p is not None:
            result.append((r.display_name, p))
    return result


async def get_providers_for_message(message: str) -> list[tuple[str, AIProvider]]:
    """
    Get providers in order for this message. If model_routing_enabled,
    consults the highest-priority model to pick the best one, then reorders.
    """
    resolved = resolve_providers_ordered()
    if not resolved:
        return []

    settings = get_settings()
    if settings.model_routing_enabled:
        from gregory.ai.selector import reorder_providers_by_model, select_model_for_message

        logger.info(
            "[model_route] Model routing enabled, consulting selector (priority 1: %s)",
            resolved[0].model,
        )
        chosen = await select_model_for_message(message)
        resolved = reorder_providers_by_model(resolved, chosen)
    else:
        logger.info(
            "[model_route] Model routing disabled, using config order: %s",
            [r.model for r in resolved],
        )

    providers = _providers_from_resolved(resolved)
    logger.info("[model_route] Provider order for this message: %s", [p[0] for p in providers])
    return providers
