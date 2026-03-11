"""Chat route - POST /users/{user_id}/chat."""

import logging
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from gregory.ai import get_provider
from gregory.ai.router import get_providers_for_message, get_providers_ordered
from gregory.ai.observations import extract_memory_markers, extract_observations
from gregory.ai.observations import HAFindRequest
from gregory.ai.prompts import build_system_prompt
from gregory.api.schemas import ChatRequest, ChatResponse
from gregory.config import get_settings
from gregory.notes.loader import load_notes_for_chat
from gregory.notes.service import NotesService
from gregory.skills.base import get_registry
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


# Broader patterns for turn on/off intent (catches "turn it back on", "turn the master bedroom lamp off", etc.)
# (?:the\s+(?:\w+(?:\s+\w+)*)) allows multi-word device names: "the master bedroom lamp"
_TURN_OFF_PATTERN = re.compile(
    r"turn\s+(?:it|that|them|the\s+(?:\w+(?:\s+\w+)*))?\s*(?:back\s+)?off|switch\s+off",
    re.IGNORECASE,
)
_TURN_ON_PATTERN = re.compile(
    r"turn\s+(?:it|that|them|the\s+(?:\w+(?:\s+\w+)*))?\s*(?:back\s+)?on|switch\s+on",
    re.IGNORECASE,
)


def _infer_ha_action(message: str, history: list | None = None) -> str | None:
    """Return 'turn_on', 'turn_off', or None if intent is unclear.

    Pronoun resolution: when the user says 'turn it on/off' or 'that didn't work',
    we infer the action from message patterns. For corrections (e.g. 'no it isn't'),
    we look at the last assistant message to determine if we previously claimed
    on or off, and return the opposite action for retry.
    """
    msg = message.lower().strip()
    if _TURN_OFF_PATTERN.search(msg):
        return "turn_off"
    if _TURN_ON_PATTERN.search(msg):
        return "turn_on"
    # User correction: "No it isn't" / "that didn't work" when we claimed it was on/off
    correction_patterns = (
        "no it isn't",
        "no it is not",
        "no it's not",
        "no you haven't",
        "that didn't work",
        "still off",
        "still on",
        "nope",
    )
    if history and any(c in msg for c in correction_patterns):
        for m in reversed(history):
            if getattr(m, "role", None) != "assistant":
                continue
            content = (getattr(m, "content", "") or "").lower()
            if "is now on" in content or "is back on" in content:
                return "turn_on"
            if "is now off" in content or "is back off" in content:
                return "turn_off"
            break
    return None


# Patterns to extract device name from assistant messages (last-mentioned device)
_LAST_DEVICE_PATTERNS = [
    re.compile(r"[Tt]he (.+?) (?:is )?(?:now|back) (?:on|off)", re.IGNORECASE),
    re.compile(r"(?:done|turned|switched)\.?\s*(?:the\s+)?(.+?)\s+(?:is\s+)?(?:now|back)\s+(?:on|off)", re.IGNORECASE),
    re.compile(r"(?:the\s+)?(.+?)\s+(?:lamp|light)\s+is\s+(?:now|back)\s+(?:on|off)", re.IGNORECASE),
    re.compile(r"(?:turned|switched)\s+off\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"(?:turned|switched)\s+on\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
    # "The X is on/off" (simple form without "now"/"back")
    re.compile(r"[Tt]he (.+?) is (?:on|off)(?:\.|$|\s)", re.IGNORECASE),
    # "I've turned on the X" / "I turned on the X"
    re.compile(r"(?:I've|I)\s+(?:turned|switched)\s+(?:on|off)\s+(?:the\s+)?(.+?)(?:\.|$)", re.IGNORECASE),
]


def _extract_last_device_from_history(history: list) -> str | None:
    """Extract the last-mentioned device name from assistant messages.

    Used for pronoun resolution: when user says 'turn it on/off' but the AI
    emitted no HA markers, we scan recent assistant messages for patterns like
    'The X is now on/off' or 'I turned on the X' to recover the device name.
    """
    for msg in reversed(history):
        if getattr(msg, "role", None) != "assistant":
            continue
        content = getattr(msg, "content", "") or ""
        for pattern in _LAST_DEVICE_PATTERNS:
            m = pattern.search(content)
            if m:
                name = m.group(1).strip()
                if name and len(name) < 80:
                    return name
    return None


def _entity_id_to_search_query(entity_id: str) -> str:
    """Derive a search query from an entity_id (e.g. light.master_bedroom_table_lamp -> master bedroom table lamp)."""
    if "." in entity_id:
        entity_id = entity_id.split(".", 1)[1]
    return entity_id.replace("_", " ").strip()


@router.post("/{user_id}/chat", response_model=ChatResponse)
async def chat(user_id: str, body: ChatRequest) -> ChatResponse:
    """Send a message as the given user and receive Gregory's response.

    Loads notes and memory context, optionally uses model routing, tries providers
    in order, runs skills (Wikipedia, web search, HA) if requested, persists journal
    entries and observations, then returns the cleaned response.
    """
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
    registry = get_registry()
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
        wikipedia_context="",
        skill_instructions=registry.build_instructions(),
        fact_check_strict=settings.fact_check_strict,
        knowledge_enabled=settings.knowledge_enabled,
        wikilinks_enabled=settings.wikilinks_enabled,
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
    successful_provider = None
    for idx, (name, provider) in enumerate(providers):
        logger.info("[chat] Trying provider %d/%d: %s", idx + 1, len(providers), name)
        try:
            response_text = await provider.generate(
                prompt=body.message,
                history=history,
                system_context=system_prompt,
            )
            successful_provider = provider
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

    # --- Memory marker extraction ---
    # Parse AI response for [JOURNAL:], [MEMORY_SEARCH:], [WIKIPEDIA:], [WEB_SEARCH:],
    # HA markers ([HA_LIST], [HA_FIND:], [HA_STATE:], [HA_SERVICE:]), and [KNOWLEDGE:].
    # Markers are stripped from the response; skill requests are processed below.
    (
        response_text,
        journal_entries,
        memory_searches,
        wikipedia_searches,
        web_searches,
        ha_list_reqs,
        ha_find_reqs,
        ha_state_reqs,
        ha_service_reqs,
        knowledge_entries,
    ) = extract_memory_markers(response_text)

    # --- HA pronoun resolution ---
    # When user says "turn it on/off" but AI emitted no HA markers, infer the device
    # from the last assistant message and add a synthetic [HA_FIND:] request.
    action = _infer_ha_action(body.message, history)
    if (
        action
        and not ha_find_reqs
        and not ha_service_reqs
        and settings.ha_enabled
        and (device := _extract_last_device_from_history(history))
    ):
        ha_find_reqs = [HAFindRequest(query=device)]
        logger.info("[chat] Pronoun resolution: inferred device %r from history", device)

    # --- Skill execution ---
    # Run Wikipedia, web search, and HA if the AI requested them; build context from
    # results, then perform a follow-up AI call for an immediate answer.
    from gregory.skills.home_assistant import HomeAssistantSkill

    ha_skill: HomeAssistantSkill | None = next(
        (s for s in registry._skills if isinstance(s, HomeAssistantSkill) and s.enabled),
        None,
    )
    has_ha_tools = bool(
        ha_skill
        and settings.ha_base_url
        and settings.ha_access_token
        and (ha_list_reqs or ha_find_reqs or ha_state_reqs or ha_service_reqs)
    )
    has_search_tools = bool(
        (wikipedia_searches or web_searches)
        and successful_provider
        and any(s.enabled for s in registry._skills if s.name in ("wikipedia", "web_search"))
    )

    if has_search_tools or has_ha_tools:
        context_parts: list[str] = []
        instruction_parts: list[str] = []

        if has_ha_tools:
            ha_result = await ha_skill.execute_batch(
                base_url=settings.ha_base_url,
                access_token=settings.ha_access_token,
                ha_list_reqs=ha_list_reqs,
                ha_find_reqs=ha_find_reqs,
                ha_state_reqs=ha_state_reqs,
                ha_service_reqs=ha_service_reqs,
                message=body.message,
                history=history,
                infer_action_fn=_infer_ha_action,
                extract_last_device_fn=_extract_last_device_from_history,
                entity_id_to_query_fn=_entity_id_to_search_query,
            )
            if ha_result.content:
                context_parts.append(ha_result.content)
                instruction_parts.append("Home Assistant results")

        # Wikipedia and web search via generic registry execution
        wiki_skill = next((s for s in registry.get_enabled_skills() if s.name == "wikipedia"), None)
        web_skill = next((s for s in registry.get_enabled_skills() if s.name == "web_search"), None)

        if wiki_skill and wikipedia_searches:
            for req in wikipedia_searches:
                try:
                    result = await wiki_skill.execute(req.query)
                    if result.content:
                        context_parts.append(result.content)
                        instruction_parts.append("Wikipedia search results")
                except Exception as e:
                    logger.warning("[chat] Wikipedia skill failed for %r: %s", req.query, e)

        if web_skill and web_searches:
            for req in web_searches:
                try:
                    result = await web_skill.execute(req.query)
                    if result.content:
                        context_parts.append(result.content)
                        instruction_parts.append("web search results")
                except Exception as e:
                    logger.warning("[chat] Web search skill failed for %r: %s", req.query, e)

        if context_parts:
            combined_context = "\n\n".join(context_parts)
            markers_note = (
                "Do not include [WIKIPEDIA: ...], [WEB_SEARCH: ...], or [HA_...] markers."
            )
            follow_up_system = (
                system_prompt
                + "\n\n"
                + combined_context
                + "\n\nUse the "
                + " and ".join(instruction_parts)
                + " above to answer the user's question. "
                "You MUST respond with natural language—state clearly what you did and the result. "
                "Never output only markers or leave the response blank. "
                + markers_note
            )
            follow_up_provider = successful_provider
            if settings.follow_up_prefer_ollama:
                all_providers = get_providers_ordered()
                ollama_first = next(
                    (p for name, p in all_providers if "ollama" in name.lower()),
                    None,
                )
                if ollama_first:
                    follow_up_provider = ollama_first
            try:
                response_text = await follow_up_provider.generate(
                    prompt=body.message,
                    history=history,
                    system_context=follow_up_system,
                )
                logger.info("[chat] Search/HA follow-up: got immediate answer")
                (
                    response_text,
                    journal_entries,
                    memory_searches,
                    wikipedia_searches,
                    web_searches,
                    ha_list_reqs,
                    ha_find_reqs,
                    ha_state_reqs,
                    ha_service_reqs,
                    knowledge_entries,
                ) = extract_memory_markers(response_text)
            except Exception as e:
                logger.warning("[chat] Search follow-up call failed: %s", e)
                if follow_up_provider != successful_provider:
                    try:
                        response_text = await successful_provider.generate(
                            prompt=body.message,
                            history=history,
                            system_context=follow_up_system,
                        )
                        logger.info("[chat] Search/HA follow-up: fallback provider succeeded")
                        (
                            response_text,
                            journal_entries,
                            memory_searches,
                            wikipedia_searches,
                            web_searches,
                            ha_list_reqs,
                            ha_find_reqs,
                            ha_state_reqs,
                            ha_service_reqs,
                            knowledge_entries,
                        ) = extract_memory_markers(response_text)
                    except Exception as e2:
                        logger.warning(
                            "[chat] Search follow-up fallback also failed: %s", e2
                        )
                        response_text = None
                # response_text: from fallback success, None (fallback failed), or original (same-provider fail)
                if not response_text or not response_text.strip():
                    response_text = (
                        "I found results but couldn't synthesize an answer. "
                        "Please try again—the search or action may have succeeded."
                    )

    # --- Persist journal entries and queue memory search results ---
    # Write [JOURNAL:] entries to disk and ChromaDB. Store [MEMORY_SEARCH:] results
    # for injection into the next user turn.
    if settings.memory_enabled:
        from gregory.memory.loader import set_pending_memory_results
        from gregory.memory.service import get_vector_store, write_journal_entry

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

    # --- Knowledge entry persistence ---
    # Write [KNOWLEDGE: title | content] entries to notes/knowledge/*.md
    if settings.knowledge_enabled and knowledge_entries:
        notes_svc_k = NotesService()
        for entry in knowledge_entries:
            try:
                notes_svc_k.append_knowledge(entry.title, entry.content)
                logger.info("[chat] Knowledge note updated: %s", entry.title)
            except Exception as e:
                logger.warning("[chat] Failed to write knowledge note %r: %s", entry.title, e)

    # --- Observation extraction ---
    # If observations_enabled: extract [OBSERVATION:], [GREGORY_NOTE:], etc. and
    # append to the appropriate notes file.
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

    # Never return empty: if the AI output only markers, use a fallback
    if not cleaned_response or not cleaned_response.strip():
        cleaned_response = "I've completed that."
        logger.warning("[chat] Response was empty after marker stripping; using fallback")

    # Persist to history (store cleaned response without observation/memory blocks)
    now = datetime.now()
    append(user_id, "user", body.message, timestamp=now)
    append(user_id, "assistant", cleaned_response, timestamp=now)

    conv_id = get_conversation_id(user_id)
    return ChatResponse(response=cleaned_response, conversation_id=conv_id)
