"""Chat route - POST /users/{user_id}/chat."""

import logging

from fastapi import APIRouter, HTTPException

from gregory.ai import get_provider
from gregory.ai.prompts import build_system_prompt
from gregory.api.schemas import ChatRequest, ChatResponse
from gregory.notes.loader import load_notes_for_chat
from gregory.notes.service import NotesService
from gregory.store import append, get_conversation_id, get_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["chat"])


@router.post("/{user_id}/chat", response_model=ChatResponse)
async def chat(user_id: str, body: ChatRequest) -> ChatResponse:
    """Send a message as the given user and receive Gregory's response."""
    provider = get_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Set OLLAMA_BASE_URL.",
        )

    # Normalize user_id for storage
    user_id = user_id.strip().lower()
    if not user_id or any(c in user_id for c in "/\\."):
        raise HTTPException(status_code=400, detail="Invalid user_id")

    # Load notes context
    notes_context = load_notes_for_chat(user_id)
    system_prompt = build_system_prompt(notes_context)

    # Get history
    history = get_history(user_id)

    # Generate response
    try:
        response_text = await provider.generate(
            prompt=body.message,
            history=history,
            system_context=system_prompt,
        )
    except Exception as e:
        logger.exception("AI generate failed: %s", e)
        raise HTTPException(status_code=502, detail="AI provider error") from e

    # Persist to history
    append(user_id, "user", body.message)
    append(user_id, "assistant", response_text)

    conv_id = get_conversation_id(user_id)
    return ChatResponse(response=response_text, conversation_id=conv_id)
