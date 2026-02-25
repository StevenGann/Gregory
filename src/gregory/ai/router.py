"""AI provider router - selects provider based on config."""

from gregory.ai.providers.base import AIProvider
from gregory.ai.providers.ollama import OllamaProvider
from gregory.config import get_settings


def get_provider() -> AIProvider | None:
    """Get the configured AI provider. Phase 1: Ollama only."""
    settings = get_settings()
    if settings.ollama_base_url:
        return OllamaProvider()
    return None
