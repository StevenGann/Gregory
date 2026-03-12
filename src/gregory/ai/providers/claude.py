"""Claude (Anthropic) AI provider — calls the Anthropic Messages API.

Uses the official ``anthropic`` Python SDK's async client (``AsyncAnthropic``).
The system prompt is passed as a top-level ``system`` parameter (not as a message
in the conversation), which is the correct pattern for Anthropic's Messages API.

The API key and model are resolved from arguments or settings. The model defaults
to ``claude-3-5-sonnet-20241022`` which balances quality and cost for general use.
"""

import logging

from anthropic import AsyncAnthropic

from gregory.ai.providers.base import AIProvider, ChatMessage, _retry_async
from gregory.config import get_settings

logger = logging.getLogger(__name__)

# Maximum tokens to generate in a single response.
# 2048 is sufficient for conversational responses; increase if Gregory needs
# to generate very long documents or code.
ANTHROPIC_MAX_TOKENS = 2048


class ClaudeProvider(AIProvider):
    """Claude provider via the Anthropic Messages API (async)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialise with explicit API key/model or fall back to settings.

        Args:
            api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
            model: Claude model identifier (e.g. ``claude-3-5-sonnet-20241022``).
        """
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key or "")
        self._model = model or settings.claude_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via the Anthropic Messages API.

        The Anthropic API separates the system prompt from conversation messages.
        System context is passed as the ``system`` parameter; conversation history
        and the current user message are passed in the ``messages`` list.

        Response shape: response.content is a list of content blocks. We extract
        text from the first TextBlock.
        """
        # Build conversation messages from history (no system message here)
        messages: list[dict[str, str]] = []
        for m in history:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": prompt})

        async def _do_request():
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                # Anthropic accepts system as a top-level param, not a message
                system=system_context or "You are Gregory, a friendly and helpful house AI assistant.",
                messages=messages,
            )
            # response.content is a list of content blocks (usually one TextBlock)
            if response.content and len(response.content) > 0:
                block = response.content[0]
                if hasattr(block, "text"):
                    return block.text.strip()
            return ""

        try:
            return await _retry_async(_do_request)
        except Exception as e:
            logger.error("Claude request failed: %s", e)
            raise
