"""Abstract AI provider interface and shared retry logic.

Defines the common contract that all AI backends (Ollama, Claude, Gemini) must
implement. Each provider is a stateless object: ``generate()`` accepts a prompt
and conversation history, and returns the model's text response.

Retry behaviour is centralised here so all providers benefit without duplication.
The retry count is read from settings at call time (default 0 = no retries), and
only transient errors (timeouts, rate limits, 429/503) trigger a retry. Permanent
errors (bad API key, invalid model) are re-raised immediately.

Retry backoff schedule: 2^attempt seconds (1s, 2s, 4s for attempts 0–2).
Configured via ``PROVIDER_RETRY_COUNT`` (0–3, default 0).
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


def _is_transient_error(exc: BaseException) -> bool:
    """Return True if the exception is a transient (retryable) error.

    Transient errors that will be retried:
    - HTTP timeouts (httpx.TimeoutException)
    - HTTP 429 (Too Many Requests / rate limit)
    - HTTP 503 (Service Unavailable)
    - Anthropic SDK: RateLimitError, APITimeoutError, APIConnectionError
    - Google SDK: DeadlineExceeded, ResourceExhausted
    - Any exception whose message contains "rate", "timeout", "503", or "429"

    Everything else (auth errors, bad requests, etc.) is considered permanent
    and will NOT be retried.
    """
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
    """Execute a coroutine factory, retrying on transient errors with exponential backoff.

    Args:
        coro_factory: A zero-argument callable that returns a new coroutine
            each time it is called. A factory (not a bare coroutine) is needed
            because coroutines cannot be re-awaited after they raise.

    Returns:
        The return value of the first successful coroutine execution.

    Raises:
        The last exception if all retry attempts are exhausted, or immediately
        if the error is not transient.
    """
    from gregory.config import get_settings

    count = get_settings().provider_retry_count
    last_exc = None
    for attempt in range(count + 1):
        try:
            return await coro_factory()
        except BaseException as e:
            last_exc = e
            if attempt < count and _is_transient_error(e):
                # Exponential backoff: 1s after attempt 0, 2s after attempt 1, 4s after attempt 2
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
