"""Chat route - POST /users/{user_id}/chat."""

import logging

from fastapi import APIRouter, HTTPException

from gregory.ai import get_provider, get_providers_ordered
from gregory.ai.observations import extract_observations
from gregory.ai.prompts import build_system_prompt
from gregory.api.schemas import ChatRequest, ChatResponse
from gregory.config import get_settings
from gregory.notes.loader import load_notes_for_chat
from gregory.notes.service import NotesService
from gregory.store import append, get_conversation_id, get_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["chat"])


def _provider_hint() -> str:
    """Hint for which config to set when no provider is available."""
    s = get_settings()
    preferred = (s.ai_provider or "").strip().lower()
    if preferred and preferred not in ("claude", "gemini", "ollama"):
        return f"AI_PROVIDER must be claude, gemini, or ollama (got: {s.ai_provider})."
    if preferred == "claude" and not s.anthropic_api_key:
        return "AI_PROVIDER=claude but ANTHROPIC_API_KEY is not set."
    if preferred == "gemini" and not s.gemini_api_key:
        return "AI_PROVIDER=gemini but GEMINI_API_KEY is not set."
    if preferred == "ollama" and not s.ollama_base_url:
        return "AI_PROVIDER=ollama but OLLAMA_BASE_URL is not set."
    return "Set OLLAMA_BASE_URL, ANTHROPIC_API_KEY, or GEMINI_API_KEY (and optionally AI_PROVIDER)."


@router.post("/{user_id}/chat", response_model=ChatResponse)
async def chat(user_id: str, body: ChatRequest) -> ChatResponse:
    """Send a message as the given user and receive Gregory's response."""
    providers = get_providers_ordered()
    if not providers:
        raise HTTPException(
            status_code=503,
            detail=f"No AI provider configured. {_provider_hint()}",
        )

    # Normalize user_id for storage
    user_id = user_id.strip().lower()
    if not user_id or any(c in user_id for c in "/\\."):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    settings = get_settings()
    notes_context = load_notes_for_chat(user_id)
    system_prompt = build_system_prompt(
        notes_context, observations_enabled=settings.observations_enabled
    )

    history = get_history(user_id)

    response_text = None
    last_error: Exception | None = None
    for name, provider in providers:
        try:
            response_text = await provider.generate(
                prompt=body.message,
                history=history,
                system_context=system_prompt,
            )
            if name != providers[0][0]:
                logger.info("Primary provider failed; succeeded with fallback: %s", name)
            break
        except Exception as e:
            logger.warning("Provider %s failed: %s", name, e)
            last_error = e

    if response_text is None:
        logger.exception("All providers failed. Last error: %s", last_error)
        raise HTTPException(status_code=502, detail="All AI providers failed") from last_error

    # Extract observations and append to notes if enabled
    cleaned_response = response_text
    if settings.observations_enabled:
        cleaned_response, observations = extract_observations(response_text)
        notes_svc = NotesService()
        for obs in observations:
            if obs:
                notes_svc.append_user(user_id, f"- {obs}")
                logger.info("Appended observation for %s: %s", user_id, obs[:50])

    # Persist to history (store cleaned response without observation blocks)
    append(user_id, "user", body.message)
    append(user_id, "assistant", cleaned_response)

    conv_id = get_conversation_id(user_id)
    return ChatResponse(response=cleaned_response, conversation_id=conv_id)
