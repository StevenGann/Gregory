"""Home Assistant skill — handles HA_LIST, HA_FIND, HA_STATE, HA_SERVICE markers.

Unlike the simple Wikipedia/WebSearch skills, Home Assistant requires coordinated
multi-step execution (e.g. HA_FIND results feed into auto-execute, failed HA_SERVICE
falls back to HA_FIND, etc.).  The Skill protocol's single execute() is satisfied for
compatibility, but chat.py calls execute_batch() to handle all HA markers together with
access to the request context (user message, history) needed for pronoun resolution.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from gregory.skills.base import SkillResult

logger = logging.getLogger(__name__)

# Individual marker patterns (also exported so chat.py can use them directly)
HA_LIST_PATTERN = re.compile(r"\[HA_LIST(?:\s*:\s*([a-zA-Z0-9_]+))?\]", re.IGNORECASE)
HA_FIND_PATTERN = re.compile(r"\[HA_FIND:\s*([^\]]+)\]", re.IGNORECASE)
HA_STATE_PATTERN = re.compile(r"\[HA_STATE:\s*([^\]]+)\]", re.IGNORECASE)
HA_SERVICE_PATTERN = re.compile(r"\[HA_SERVICE:\s*([^\]]+)\]", re.IGNORECASE)

# Combined pattern: matches any HA marker (group 1 = first capture group of whichever matched)
_ANY_HA = re.compile(
    r"\[HA_(?:LIST|FIND|STATE|SERVICE)[^\]]*\]",
    re.IGNORECASE,
)

INSTRUCTION = """
## Home Assistant control

You can interact with the home automation system (lights, sensors, switches, etc.) using these markers:

- **[HA_FIND: query]** — search entities by friendly name (e.g. "front door", "living room light"). Use this first when the user mentions a device by name and you don't know the exact entity_id.
- **[HA_LIST]** or **[HA_LIST: domain]** — list entities. Use a domain (e.g. light, sensor, switch) to filter.
- **[HA_STATE: entity_id]** — get current state of an entity.
- **[HA_SERVICE: domain.service | key=value | ...]** — call a service.

**When the user asks about something by name (e.g. "front door", "kitchen light"):** Use [HA_FIND: query] first to find the correct entity_id, then use [HA_STATE] or [HA_SERVICE] with that entity_id.

**When the user says "turn it on/off" or "turn it back on":** Use the device name from the most recent exchange. If you just said "The Master Bedroom Table Lamp is now off", the user's "turn it back on" refers to that lamp—emit [HA_FIND: Master Bedroom Table Lamp] so the command can execute. Never reply "Done" without emitting HA markers; the command will not execute.

**Important:** Emit HA markers in your FIRST response so the user gets the answer immediately. Do not say "I'll check" and wait for a follow-up—include the markers in the same reply.

**If a user says a command didn't work:** Use [HA_FIND: device name] first to get the correct entity_id. Never guess entity_id from the friendly name (e.g. "Master Bedroom Table Lamp" is NOT light.master_bedroom_table_lamp—the real id may be light.smart_rgbtw_bulb_4). After finding the entity, use [HA_STATE: entity_id] or [HA_SERVICE: light.turn_on | entity_id=...] with the actual entity_id. If the state didn't change, the device may be offline or unresponsive—report what you see.

**When [HA_FIND] returns "All lights in the system" (no match):** Use that list to help the user. Point out likely candidates by entity_id or friendly_name (e.g. "light.smart_rgbtw_bulb_4 might be the one in the master bedroom—shall I turn that off?"). Offer to act on a specific entity_id if the user confirms.

**Examples:**
- `[HA_FIND: front door]` — find entities matching "front door"
- `[HA_FIND: living room light]` — find lights in living room
- `[HA_LIST: light]` — list all lights
- `[HA_STATE: sensor.temperature_living_room]` — read a sensor
- `[HA_SERVICE: light.turn_on | entity_id=light.living_room]` — turn on a light
- `[HA_SERVICE: light.turn_off | entity_id=light.living_room]` — turn off
- `[HA_SERVICE: light.turn_on | entity_id=light.living_room | brightness=128 | color_temp_kelvin=3000]` — dim to 50% and set warm white (brightness 1-255, color_temp_kelvin typically 2000-6500)
- `[HA_SERVICE: light.turn_on | entity_id=light.kitchen | rgb_color=255,128,0]` — set color (R,G,B 0-255)
- `[HA_SERVICE: light.turn_on | entity_id=light.x | transition=2]` — fade over 2 seconds

For lights: brightness (1-255), color_temp_kelvin (warm to cool), rgb_color (R,G,B). Use multiple markers if needed."""


class HomeAssistantSkill:
    """Skill encapsulating all Home Assistant marker handling.

    chat.py calls execute_batch() rather than the generic Skill.execute() so that
    cross-marker coordination (pronoun resolution, 404 fallback, auto-execute) can
    access the request message and history.
    """

    name = "home_assistant"
    marker_pattern = _ANY_HA  # satisfies Skill protocol; execute() handles single marker
    instruction = INSTRUCTION
    enabled: bool = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def execute(self, query: str) -> SkillResult:
        """Satisfy Skill protocol. Returns empty result; real execution via execute_batch()."""
        return SkillResult(
            skill_name=self.name,
            query=query,
            content="",
            success=True,
        )

    async def execute_batch(
        self,
        base_url: str,
        access_token: str,
        ha_list_reqs: list,
        ha_find_reqs: list,
        ha_state_reqs: list,
        ha_service_reqs: list,
        message: str = "",
        history: list | None = None,
        infer_action_fn=None,
        extract_last_device_fn=None,
        entity_id_to_query_fn=None,
    ) -> SkillResult:
        """Execute all HA requests with full coordination and fallback logic.

        Parameters mirror the data extracted from the AI response plus the request
        context needed for pronoun resolution and fallback.

        Returns a SkillResult whose .content is the formatted HA context block.
        """
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

        # HA_FIND
        for req in ha_find_reqs:
            try:
                ents = await find_entities(base_url, access_token, req.query)
                find_results[req.query] = ents
                if not ents:
                    fallback = await list_entities(base_url, access_token, domain="light")
                    find_fallbacks[req.query] = fallback
            except Exception as e:
                logger.warning("[ha_skill] find_entities failed for %r: %s", req.query, e)
                find_results[req.query] = []

        # HA_LIST
        for req in ha_list_reqs:
            try:
                ents = await list_entities(base_url, access_token, domain=req.domain)
                list_results.extend(ents)
            except Exception as e:
                logger.warning("[ha_skill] list_entities failed: %s", e)

        # HA_STATE
        for req in ha_state_reqs:
            try:
                state = await get_state(base_url, access_token, req.entity_id)
                state_results.append(state)
            except Exception as e:
                logger.warning("[ha_skill] get_state failed for %s: %s", req.entity_id, e)
                state_results.append(None)

        # HA_SERVICE
        for req in ha_service_reqs:
            parsed = parse_service_params(req.params_str)
            if parsed:
                domain, service, data = parsed
                try:
                    ok, msg = await call_service(base_url, access_token, domain, service, data)
                    service_results.append((ok, msg))
                except Exception as e:
                    logger.warning("[ha_skill] call_service failed: %s", e)
                    service_results.append((False, str(e)))
            else:
                service_results.append((False, f"Failed to parse: {req.params_str}"))

        # --- HA_SERVICE failure fallback ---
        action = infer_action_fn(message, history) if infer_action_fn else None
        if ha_service_reqs and action:
            for failed_idx, (ok, msg) in enumerate(service_results):
                if ok:
                    continue
                err_msg = msg.lower()
                if "not found" not in err_msg and "404" not in err_msg and "entity" not in err_msg:
                    continue
                if failed_idx >= len(ha_service_reqs):
                    continue
                req = ha_service_reqs[failed_idx]
                parsed = parse_service_params(req.params_str)
                bad_entity_id: str | None = None
                if parsed and isinstance(parsed[2].get("entity_id"), str):
                    bad_entity_id = parsed[2]["entity_id"]
                elif parsed and isinstance(parsed[2].get("entity_id"), list):
                    bad_entity_id = parsed[2]["entity_id"][0] if parsed[2]["entity_id"] else None
                device = extract_last_device_fn(history) if extract_last_device_fn else None
                if not device and bad_entity_id and entity_id_to_query_fn:
                    device = entity_id_to_query_fn(bad_entity_id)
                if not device:
                    continue
                try:
                    ents = await find_entities(base_url, access_token, device)
                    if len(ents) == 1:
                        ent = ents[0]
                        entity_id = ent.get("entity_id")
                        if entity_id and "." in entity_id:
                            domain = entity_id.split(".", 1)[0]
                            ok2, msg2 = await call_service(
                                base_url, access_token, domain, action, {"entity_id": entity_id}
                            )
                            service_results[failed_idx] = (ok2, msg2)
                            logger.info("[ha_skill] HA_SERVICE fallback: retried with %s", entity_id)
                except Exception as e:
                    logger.warning("[ha_skill] HA_SERVICE fallback failed for %r: %s", device, e)

        # --- HA_STATE 404 fallback ---
        action = infer_action_fn(message, history) if infer_action_fn else None
        if action and not ha_service_reqs:
            for i, state in enumerate(state_results):
                if not state or state.get("error") != "not found":
                    continue
                failed_entity_id = ha_state_reqs[i].entity_id if i < len(ha_state_reqs) else ""
                device = extract_last_device_fn(history) if extract_last_device_fn else None
                if not device and failed_entity_id and entity_id_to_query_fn:
                    device = entity_id_to_query_fn(failed_entity_id)
                if not device:
                    continue
                if device in find_results or any(r.query == device for r in ha_find_reqs):
                    continue
                try:
                    ents = await find_entities(base_url, access_token, device)
                    if ents:
                        ha_find_reqs.append(type("_Req", (), {"query": device})())
                        find_results[device] = ents
                        logger.info("[ha_skill] HA_STATE 404 fallback: resolved %r", device)
                except Exception as e:
                    logger.warning("[ha_skill] HA_STATE 404 fallback find failed for %r: %s", device, e)

        # --- Auto-execute turn intent ---
        action = infer_action_fn(message, history) if infer_action_fn else None
        if not ha_service_reqs and len(ha_find_reqs) == 1 and action:
            req = ha_find_reqs[0]
            ents = find_results.get(req.query, [])
            if len(ents) == 1:
                ent = ents[0]
                entity_id = ent.get("entity_id")
                if entity_id and "." in entity_id:
                    domain = entity_id.split(".", 1)[0]
                    try:
                        ok, msg = await call_service(
                            base_url, access_token, domain, action, {"entity_id": entity_id}
                        )
                        service_results.append((ok, msg))
                        logger.info("[ha_skill] Auto-executed %s.%s for %s", domain, action, entity_id)
                    except Exception as e:
                        logger.warning("[ha_skill] Auto-execute failed for %s: %s", entity_id, e)
                        service_results.append((False, str(e)))

        content = format_ha_context(
            list_results,
            state_results,
            service_results,
            find_results=find_results or None,
            find_fallbacks=find_fallbacks or None,
        )
        return SkillResult(
            skill_name=self.name,
            query="<batch>",
            content=content,
            success=True,
        )
