"""Chat route - POST /users/{user_id}/chat."""

import logging
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException

from gregory.ai import get_provider
from gregory.ai.router import get_providers_for_message
from gregory.ai.observations import extract_memory_markers, extract_observations
from gregory.ai.observations import HAFindRequest
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
    """Return 'turn_on', 'turn_off', or None if intent is unclear."""
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
    Used when user says 'turn it on/off' but the AI emits no HA markers."""
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
        wikipedia_context="",
        wikipedia_enabled=settings.wikipedia_enabled,
        web_search_enabled=settings.web_search_enabled,
        fact_check_strict=settings.fact_check_strict,
        ha_enabled=settings.ha_enabled,
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

    # Extract memory markers ([JOURNAL:], [MEMORY_SEARCH:], [WIKIPEDIA:], [WEB_SEARCH:], HA markers) FIRST
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
    ) = extract_memory_markers(response_text)

    # Pronoun resolution: when user says "turn it on/off" but AI emitted no HA markers,
    # infer the device from the last assistant message and add a synthetic find request
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

    # Wikipedia and/or web search and/or HA: run tools and do follow-up call for immediate answer
    has_ha_tools = (
        settings.ha_enabled
        and settings.ha_base_url
        and settings.ha_access_token
        and (ha_list_reqs or ha_find_reqs or ha_state_reqs or ha_service_reqs)
    )
    has_search_tools = (wikipedia_searches or web_searches) and successful_provider
    if (
        (has_search_tools and (settings.wikipedia_enabled or settings.web_search_enabled))
        or has_ha_tools
    ):
        context_parts: list[str] = []
        instruction_parts: list[str] = []

        if has_ha_tools:
            from gregory.tools.home_assistant import (
                call_service,
                find_entities,
                format_ha_context,
                get_state,
                list_entities,
                parse_service_params,
            )

            list_results: list[dict] = []
            find_results: dict[str, list[dict]] = {}
            find_fallbacks: dict[str, list[dict]] = {}
            state_results: list[dict | None] = []
            service_results: list[tuple[bool, str]] = []

            for req in ha_find_reqs:
                try:
                    ents = await find_entities(
                        settings.ha_base_url,
                        settings.ha_access_token,
                        req.query,
                    )
                    find_results[req.query] = ents
                    if not ents:
                        fallback = await list_entities(
                            settings.ha_base_url,
                            settings.ha_access_token,
                            domain="light",
                        )
                        find_fallbacks[req.query] = fallback
                except Exception as e:
                    logger.warning("[chat] HA find_entities failed for %r: %s", req.query, e)
                    find_results[req.query] = []

            for req in ha_list_reqs:
                try:
                    ents = await list_entities(
                        settings.ha_base_url,
                        settings.ha_access_token,
                        domain=req.domain,
                    )
                    list_results.extend(ents)
                except Exception as e:
                    logger.warning("[chat] HA list_entities failed: %s", e)

            for req in ha_state_reqs:
                try:
                    state = await get_state(
                        settings.ha_base_url,
                        settings.ha_access_token,
                        req.entity_id,
                    )
                    state_results.append(state)
                except Exception as e:
                    logger.warning("[chat] HA get_state failed for %s: %s", req.entity_id, e)
                    state_results.append(None)

            for req in ha_service_reqs:
                parsed = parse_service_params(req.params_str)
                if parsed:
                    domain, service, data = parsed
                    try:
                        ok, msg = await call_service(
                            settings.ha_base_url,
                            settings.ha_access_token,
                            domain,
                            service,
                            data,
                        )
                        service_results.append((ok, msg))
                    except Exception as e:
                        logger.warning("[chat] HA call_service failed: %s", e)
                        service_results.append((False, str(e)))
                else:
                    service_results.append((False, f"Failed to parse: {req.params_str}"))

            # HA_SERVICE failure fallback: AI used wrong entity_id, call failed. Retry via HA_FIND.
            action = _infer_ha_action(body.message, history)
            if ha_service_reqs and action and service_results:
                failed_idx = next(
                    (i for i, (ok, msg) in enumerate(service_results) if not ok),
                    None,
                )
                if failed_idx is not None:
                    err_msg = service_results[failed_idx][1].lower()
                    if "not found" in err_msg or "404" in err_msg or "entity" in err_msg:
                        req = ha_service_reqs[failed_idx]
                        parsed = parse_service_params(req.params_str)
                        bad_entity_id = (
                            parsed[2].get("entity_id")
                            if parsed and isinstance(parsed[2].get("entity_id"), str)
                            else None
                        )
                        if not bad_entity_id and parsed and isinstance(parsed[2].get("entity_id"), list):
                            bad_entity_id = parsed[2]["entity_id"][0] if parsed[2]["entity_id"] else None
                        device = _extract_last_device_from_history(history)
                        if not device and bad_entity_id:
                            device = _entity_id_to_search_query(bad_entity_id)
                        if device:
                            try:
                                ents = await find_entities(
                                    settings.ha_base_url,
                                    settings.ha_access_token,
                                    device,
                                )
                                if len(ents) == 1:
                                    ent = ents[0]
                                    entity_id = ent.get("entity_id")
                                    if entity_id and "." in entity_id:
                                        domain = entity_id.split(".", 1)[0]
                                        ok, msg = await call_service(
                                            settings.ha_base_url,
                                            settings.ha_access_token,
                                            domain,
                                            action,
                                            {"entity_id": entity_id},
                                        )
                                        service_results[failed_idx] = (ok, msg)
                                        logger.info(
                                            "[chat] HA_SERVICE fallback: retried with %s",
                                            entity_id,
                                        )
                            except Exception as e:
                                logger.warning(
                                    "[chat] HA_SERVICE fallback failed for %r: %s",
                                    device,
                                    e,
                                )

            # HA_STATE 404 fallback: AI guessed entity_id (e.g. light.master_bedroom_table_lamp), got 404.
            # Resolve via HA_FIND and auto-execute if we have turn intent.
            action = _infer_ha_action(body.message, history)
            for i, state in enumerate(state_results):
                if state and state.get("error") == "not found" and action and not ha_service_reqs:
                    failed_entity_id = ha_state_reqs[i].entity_id if i < len(ha_state_reqs) else ""
                    device = _extract_last_device_from_history(history)
                    if not device and failed_entity_id:
                        device = _entity_id_to_search_query(failed_entity_id)
                    if device and not ha_find_reqs:
                        try:
                            ents = await find_entities(
                                settings.ha_base_url,
                                settings.ha_access_token,
                                device,
                            )
                            if ents:
                                ha_find_reqs = [HAFindRequest(query=device)]
                                find_results[device] = ents
                                logger.info(
                                    "[chat] HA_STATE 404 fallback: resolved %r via HA_FIND",
                                    device,
                                )
                                break
                        except Exception as e:
                            logger.warning(
                                "[chat] HA_STATE 404 fallback find failed for %r: %s",
                                device,
                                e,
                            )
                    break

            # Auto-execute turn_on/turn_off when HA_FIND returns exactly one match and user intent is clear
            if (
                not ha_service_reqs
                and len(ha_find_reqs) == 1
                and (action := _infer_ha_action(body.message, history))
            ):
                req = ha_find_reqs[0]
                ents = find_results.get(req.query, [])
                if len(ents) == 1:
                    ent = ents[0]
                    entity_id = ent.get("entity_id")
                    if entity_id and "." in entity_id:
                        domain = entity_id.split(".", 1)[0]
                        try:
                            ok, msg = await call_service(
                                settings.ha_base_url,
                                settings.ha_access_token,
                                domain,
                                action,
                                {"entity_id": entity_id},
                            )
                            service_results.append((ok, msg))
                            logger.info(
                                "[chat] HA auto-executed %s.%s for %s",
                                domain,
                                action,
                                entity_id,
                            )
                        except Exception as e:
                            logger.warning(
                                "[chat] HA auto-execute failed for %s: %s",
                                entity_id,
                                e,
                            )
                            service_results.append((False, str(e)))

            ha_context = format_ha_context(
                list_results,
                state_results,
                service_results,
                find_results=find_results or None,
                find_fallbacks=find_fallbacks or None,
            )
            if ha_context:
                context_parts.append(ha_context)
                instruction_parts.append("Home Assistant results")

        if settings.wikipedia_enabled and wikipedia_searches:
            from gregory.tools.wikipedia import format_wikipedia_context, search_wikipedia

            all_wiki_results: list[dict] = []
            for req in wikipedia_searches:
                try:
                    results = await search_wikipedia(req.query, max_results=3)
                    all_wiki_results.extend(results)
                except Exception as e:
                    logger.warning("[chat] Wikipedia search failed for %r: %s", req.query, e)

            wiki_context = format_wikipedia_context(all_wiki_results)
            if wiki_context:
                context_parts.append(wiki_context)
                instruction_parts.append("Wikipedia search results")
            else:
                context_parts.append("## Wikipedia search results\n\nNo results found.")
                instruction_parts.append("Wikipedia search (no results)")

        if settings.web_search_enabled and web_searches:
            from gregory.tools.web_search import format_web_search_context, search_web

            all_web_results: list[dict] = []
            for req in web_searches:
                try:
                    results = await search_web(req.query, max_results=5)
                    all_web_results.extend(results)
                except Exception as e:
                    logger.warning("[chat] Web search failed for %r: %s", req.query, e)

            web_context = format_web_search_context(all_web_results)
            if web_context:
                context_parts.append(web_context)
                instruction_parts.append("web search results")
            else:
                context_parts.append("## Web search results\n\nNo results found.")
                instruction_parts.append("web search (no results)")

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
            try:
                response_text = await successful_provider.generate(
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
                ) = extract_memory_markers(response_text)
            except Exception as e:
                logger.warning("[chat] Search follow-up call failed: %s", e)

    # Process journal entries and memory searches (from final response, after any Wikipedia follow-up)
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
