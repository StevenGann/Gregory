"""AI provider router - selects provider based on config."""

from gregory.ai.providers.base import AIProvider
from gregory.ai.providers.claude import ClaudeProvider
from gregory.ai.providers.gemini import GeminiProvider
from gregory.ai.providers.ollama import OllamaProvider
from gregory.config import get_settings


def get_provider() -> AIProvider | None:
    """Get the configured AI provider. Priority: explicit ai_provider, then Claude, Gemini, Ollama."""
    settings = get_settings()
    preferred = (settings.ai_provider or "").strip().lower()

    def use(p: str) -> bool:
        return not preferred or preferred == p

    if use("claude") and settings.anthropic_api_key:
        return ClaudeProvider()
    if use("gemini") and settings.gemini_api_key:
        return GeminiProvider()
    if use("ollama") and settings.ollama_base_url:
        return OllamaProvider()
    return None
