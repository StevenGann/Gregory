"""Ollama AI provider."""

import logging
from typing import Any

import httpx

from gregory.ai.providers.base import AIProvider, ChatMessage, _retry_async
from gregory.config import get_settings

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT = 120.0


class OllamaProvider(AIProvider):
    """Ollama provider using REST API."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.ollama_base_url or "").rstrip("/")
        self._model = model or settings.ollama_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via Ollama chat API."""
        messages: list[dict[str, str]] = []

        if system_context:
            messages.append({"role": "system", "content": system_context})

        for m in history:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        url = f"{self._base_url}/api/chat"

        async def _do_request():
            async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
                r = await client.post(url, json=body)
                r.raise_for_status()
                data = r.json()
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
