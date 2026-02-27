"""Gemini (Google) AI provider."""

import logging

import google.generativeai as genai

from gregory.ai.providers.base import AIProvider, ChatMessage
from gregory.config import get_settings

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Gemini provider via Google Generative AI."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key or settings.gemini_api_key or ""
        genai.configure(api_key=key)
        self._model_name = model or settings.gemini_model

    async def generate(
        self,
        prompt: str,
        history: list[ChatMessage],
        system_context: str = "",
    ) -> str:
        """Generate response via Gemini chat API."""
        model = genai.GenerativeModel(
            self._model_name,
            system_instruction=system_context
            or "You are Gregory, a friendly and helpful house AI assistant.",
        )

        # Gemini uses "user" and "model" for roles
        gemini_history: list[dict] = []
        for m in history:
            role = "user" if m.role == "user" else "model"
            gemini_history.append({"role": role, "parts": [m.content]})

        try:
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(prompt)
            return (response.text or "").strip()
        except Exception as e:
            logger.error("Gemini request failed: %s", e)
            raise
