"""Abstract AI provider interface."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


def _is_transient_error(exc: BaseException) -> bool:
    """Return True if the exception is transient (retryable)."""
    try:
        import httpx

        if isinstance(exc, httpx.TimeoutException):
            return True
    except ImportError:
        pass
    if hasattr(exc, "status_code") and getattr(exc, "status_code") in (429, 503):
        return True
    name = type(exc).__name__
    if any(
        x in name
        for x in (
            "RateLimitError",
            "APITimeoutError",
            "APIConnectionError",
            "DeadlineExceeded",
            "ResourceExhausted",
        )
    ):
        return True
    msg = str(exc).lower()
    if "rate" in msg or "timeout" in msg or "503" in msg or "429" in msg:
        return True
    return False


async def _retry_async(coro_factory):
    """Execute coroutine from factory, retrying on transient errors. Factory is a callable returning an awaitable."""
    from gregory.config import get_settings

    count = get_settings().provider_retry_count
    last_exc = None
    for attempt in range(count + 1):
        try:
            return await coro_factory()
        except BaseException as e:
            last_exc = e
            if attempt < count and _is_transient_error(e):
                delay = 2**attempt
                await asyncio.sleep(delay)
                continue
            raise
    if last_exc:
        raise last_exc


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
