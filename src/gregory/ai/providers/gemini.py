"""Gemini (Google) AI provider."""

import logging

from google import genai
from google.genai import types

from gregory.ai.providers.base import AIProvider, ChatMessage, _retry_async
from gregory.config import get_settings

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Gemini provider via Google Gen AI SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key or settings.gemini_api_key or ""
        self._client = genai.Client(api_key=key)
        self._model_name = model or settings.gemini_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via Gemini chat API."""
        # Build history as list of Content
        gemini_history: list[types.Content] = []
        for m in history:
            role = "user" if m.role == "user" else "model"
            gemini_history.append(
                types.Content(role=role, parts=[types.Part.from_text(text=m.content)])
            )

        config = types.GenerateContentConfig(
            system_instruction=system_context
            or "You are Gregory, a friendly and helpful house AI assistant.",
        )

        async def _do_request():
            chat = self._client.aio.chats.create(
                model=self._model_name,
                config=config,
                history=gemini_history,
            )
            response = await chat.send_message(prompt)
            return (response.text or "").strip()

        try:
            return await _retry_async(_do_request)
        except Exception as e:
            logger.error("Gemini request failed: %s", e)
            raise
