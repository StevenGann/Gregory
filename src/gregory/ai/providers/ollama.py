"""Ollama AI provider — calls a local or remote Ollama server via its REST API.

Ollama is a self-hosted model runner. This provider uses the ``POST /api/chat``
endpoint with ``stream: false`` so the full response is returned in a single JSON
body, avoiding the complexity of streaming response parsing.

The base URL and model can be set explicitly (e.g. when using multi-provider
config) or fall back to ``OLLAMA_BASE_URL`` and ``OLLAMA_MODEL`` from settings.

Ollama is free to run and is typically configured as the primary or cost-saving
provider in multi-provider setups.
"""

import logging
from typing import Any

import httpx

from gregory.ai.providers.base import AIProvider, ChatMessage, _retry_async
from gregory.config import get_settings

logger = logging.getLogger(__name__)

# Maximum seconds to wait for an Ollama response. Larger models on slower hardware
# can take significant time to generate a response, so this is set generously.
OLLAMA_TIMEOUT = 120.0


class OllamaProvider(AIProvider):
    """Ollama provider using the Ollama REST chat API (POST /api/chat)."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        """Initialise with explicit URL/model or fall back to settings.

        Args:
            base_url: Ollama server URL (e.g. ``http://localhost:11434``).
                Trailing slash is stripped for consistent URL construction.
            model: Model name as understood by Ollama (e.g. ``llama3.2``).
        """
        settings = get_settings()
        self._base_url = (base_url or settings.ollama_base_url or "").rstrip("/")
        self._model = model or settings.ollama_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via Ollama chat API.

        Builds the message list in Ollama's expected format:
          [system_message?, ...history_messages, current_user_message]

        Streaming is disabled so the full response is returned as one JSON object.
        """
        messages: list[dict[str, str]] = []

        # System message must be first, before any conversation turns
        if system_context:
            messages.append({"role": "system", "content": system_context})

        # Append full conversation history so the model has multi-turn context
        for m in history:
            messages.append({"role": m.role, "content": m.content})

        # Append the current user message last
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,  # Return complete response, not streamed chunks
        }

        url = f"{self._base_url}/api/chat"

        async def _do_request():
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                r = await client.post(url, json=body)
                r.raise_for_status()
                data = r.json()
                # Ollama response shape: {"message": {"role": "assistant", "content": "..."}}
                msg = data.get("message", {})
                content = msg.get("content", "")
                return content.strip() if isinstance(content, str) else ""

        try:
            return await _retry_async(_do_request)
        except httpx.HTTPError as e:
            logger.error("Ollama request failed: %s", e)
            raise
        except Exception as e:
            logger.error("Ollama error: %s", e)
            raise
