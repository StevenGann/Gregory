"""Gemini (Google) AI provider — calls the Google Gen AI API.

Uses the ``google-genai`` SDK's async chat interface. The SDK requires
conversation history to be provided as ``types.Content`` objects with Gemini's
role conventions: ``"user"`` for human turns and ``"model"`` (not "assistant")
for AI turns.

The system instruction is provided via ``GenerateContentConfig``, which is the
correct mechanism for the new Google Gen AI SDK (distinct from older PaLM-era
APIs that used a different system prompt pattern).
"""

import logging

from google import genai
from google.genai import types

from gregory.ai.providers.base import AIProvider, ChatMessage, _retry_async
from gregory.config import get_settings

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Gemini provider via the Google Gen AI SDK (async chat interface)."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialise with explicit API key/model or fall back to settings.

        Args:
            api_key: Google API key. Falls back to ``GEMINI_API_KEY`` env var.
            model: Gemini model identifier (e.g. ``gemini-1.5-flash``).
        """
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
        """Generate response via the Gemini async chat API.

        Converts conversation history from Gregory's internal ``ChatMessage``
        format to Gemini's ``types.Content`` format. Note that Gemini uses
        ``"model"`` (not ``"assistant"``) as the role name for AI turns.

        The system instruction is set in ``GenerateContentConfig`` and persists
        for the duration of the chat session.
        """
        # Convert Gregory history to Gemini Content objects.
        # Gemini role names: "user" for human, "model" for AI responses.
        gemini_history: list[types.Content] = []
        for m in history:
            role = "user" if m.role == "user" else "model"
            gemini_history.append(
                types.Content(role=role, parts=[types.Part.from_text(text=m.content)])
            )

        # System instruction is provided at session creation time, not as a message
        config = types.GenerateContentConfig(
            system_instruction=system_context
            or "You are Gregory, a friendly and helpful house AI assistant.",
        )

        async def _do_request():
            # Create a new async chat session with history and system config
            chat = self._client.aio.chats.create(
                model=self._model_name,
                config=config,
                history=gemini_history,
            )
            # Send the current user message and await the full response
            response = await chat.send_message(prompt)
            return (response.text or "").strip()

        try:
            return await _retry_async(_do_request)
        except Exception as e:
            logger.error("Gemini request failed: %s", e)
            raise
