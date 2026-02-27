"""AI provider router - selects provider based on config."""

from gregory.ai.providers.base import AIProvider
from gregory.ai.providers.claude import ClaudeProvider
from gregory.ai.providers.gemini import GeminiProvider
from gregory.ai.providers.ollama import OllamaProvider
from gregory.config import get_settings

_PROVIDERS = [
    ("claude", ClaudeProvider, lambda s: s.anthropic_api_key),
    ("gemini", GeminiProvider, lambda s: s.gemini_api_key),
    ("ollama", OllamaProvider, lambda s: s.ollama_base_url),
]


def get_provider() -> AIProvider | None:
    """Get the primary configured AI provider. Used for health check and single-provider logic."""
    providers = get_providers_ordered()
    return providers[0][1] if providers else None


def get_providers_ordered() -> list[tuple[str, AIProvider]]:
    """Get all configured providers in fallback order. Primary first, then alternatives on failure."""
    settings = get_settings()
    preferred = (settings.ai_provider or "").strip().lower()

    # Build ordered list: preferred first (if set), then rest by default order
    order = ["claude", "gemini", "ollama"]
    if preferred and preferred in order:
        order = [preferred] + [p for p in order if p != preferred]

    result: list[tuple[str, AIProvider]] = []
    for name in order:
        for pname, pcls, enabled in _PROVIDERS:
            if pname == name and enabled(settings):
                result.append((pname, pcls()))
                break
    return result
