"""AI provider abstraction and implementations."""

from gregory.ai.providers.base import AIProvider, ChatMessage
from gregory.ai.providers.ollama import OllamaProvider
from gregory.ai.router import get_provider

__all__ = ["AIProvider", "ChatMessage", "OllamaProvider", "get_provider"]
