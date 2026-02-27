"""Chat route - POST /users/{user_id}/chat."""

import logging

from fastapi import APIRouter, HTTPException

from gregory.ai import get_provider
from gregory.ai.router import get_providers_for_message
from gregory.ai.observations import extract_memory_markers, extract_observations
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
    providers = await get_providers_for_message(body.message)
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

    # Memory retrieval: vector-search for relevant past journal entries
    memory_context = ""
    if settings.memory_enabled:
        from gregory.memory.loader import load_memory_for_chat
        from gregory.memory.service import get_vector_store
        try:
            memory_context = await load_memory_for_chat(
                user_id=user_id,
                message=body.message,
                vector_store=get_vector_store(),
            )
        except Exception as e:
            logger.warning("[chat] Memory retrieval failed: %s", e)

    system_prompt = build_system_prompt(
        notes_context,
        observations_enabled=settings.observations_enabled,
        user_id=user_id,
        memory_context=memory_context,
        memory_enabled=settings.memory_enabled,
    )

    history = get_history(user_id)

    provider_order = [p[0] for p in providers]
    logger.info(
        "[chat] user=%s trying providers in order: %s",
        user_id,
        provider_order,
    )

    response_text = None
    last_error: Exception | None = None
    for idx, (name, provider) in enumerate(providers):
        logger.info("[chat] Trying provider %d/%d: %s", idx + 1, len(providers), name)
        try:
            response_text = await provider.generate(
                prompt=body.message,
                history=history,
                system_context=system_prompt,
            )
            if idx == 0:
                logger.info("[chat] Success with primary provider: %s", name)
            else:
                logger.info("[chat] Success with fallback provider %d: %s (primary failed)", idx + 1, name)
            break
        except Exception as e:
            logger.warning("[chat] Provider %s failed: %s", name, e)
            last_error = e

    if response_text is None:
        logger.exception("All providers failed. Last error: %s", last_error)
        raise HTTPException(status_code=502, detail="All AI providers failed") from last_error

    # Extract memory markers ([JOURNAL:] and [MEMORY_SEARCH:]) FIRST
    if settings.memory_enabled:
        from gregory.ai.observations import extract_memory_markers
        from gregory.memory.loader import set_pending_memory_results
        from gregory.memory.service import get_vector_store, write_journal_entry

        response_text, journal_entries, memory_searches = extract_memory_markers(response_text)

        for entry in journal_entries:
            try:
                await write_journal_entry(entry.content, user_id=user_id)
                logger.info("[chat] Journal entry written: %s", entry.content[:60])
            except Exception as e:
                logger.warning("[chat] Failed to write journal entry: %s", e)

        if memory_searches:
            vector_store = get_vector_store()
            all_results: list[dict] = []
            for req in memory_searches:
                try:
                    results = await vector_store.search(req.query, n_results=5, threshold=0.0)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning("[chat] Memory search failed for %r: %s", req.query, e)
            if all_results:
                set_pending_memory_results(user_id, all_results)
                logger.info("[chat] Stored %d memory search results for next turn", len(all_results))

    # Extract observations and append to notes if enabled
    cleaned_response = response_text
    if settings.observations_enabled:
        cleaned_response, observations = extract_observations(response_text)
        notes_svc = NotesService()
        for obs in observations:
            if not obs.content:
                continue
            line = f"- {obs.content}"
            if obs.target == "user":
                notes_svc.append_user(user_id, line)
                logger.info("Appended observation for %s: %s", user_id, obs.content[:50])
            elif obs.target == "gregory":
                notes_svc.append_gregory(line)
                logger.info("Appended Gregory note: %s", obs.content[:50])
            elif obs.target == "household":
                notes_svc.append_household(line)
                logger.info("Appended household note: %s", obs.content[:50])
            else:
                notes_svc.append_entity(obs.target, line)
                logger.info("Appended entity note for %s: %s", obs.target, obs.content[:50])

    # Persist to history (store cleaned response without observation/memory blocks)
    append(user_id, "user", body.message)
    append(user_id, "assistant", cleaned_response)

    conv_id = get_conversation_id(user_id)
    return ChatResponse(response=cleaned_response, conversation_id=conv_id)
