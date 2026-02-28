"""Abstract AI provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """Single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime | None = None


class AIProvider(ABC):
    """Abstract base for AI providers (Ollama, Claude, Gemini)."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate a response given the prompt, conversation history, and optional system context."""
        ...
