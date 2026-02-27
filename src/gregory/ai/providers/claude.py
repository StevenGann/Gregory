"""Claude (Anthropic) AI provider."""

import logging

from anthropic import AsyncAnthropic

from gregory.ai.providers.base import AIProvider, ChatMessage
from gregory.config import get_settings

logger = logging.getLogger(__name__)

ANTHROPIC_MAX_TOKENS = 2048


class ClaudeProvider(AIProvider):
    """Claude provider via Anthropic API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key or "")
        self._model = model or settings.claude_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via Anthropic Messages API."""
        messages: list[dict[str, str]] = []
        for m in history:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system_context or "You are Gregory, a friendly and helpful house AI assistant.",
                messages=messages,
            )
            if response.content and len(response.content) > 0:
                block = response.content[0]
                if hasattr(block, "text"):
                    return block.text.strip()
            return ""
        except Exception as e:
            logger.error("Claude request failed: %s", e)
            raise
