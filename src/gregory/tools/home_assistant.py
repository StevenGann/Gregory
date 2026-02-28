"""Home Assistant REST API client for Gregory."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def parse_service_params(params_str: str) -> tuple[str, str, dict[str, Any]] | None:
    """Parse [HA_SERVICE: domain.service | key1=val1 | key2=val2] into (domain, service, data).

    Returns None if parsing fails.
    """
    parts = [p.strip() for p in params_str.split("|") if p.strip()]
    if not parts:
        return None
    domain_service = parts[0]
    if "." not in domain_service:
        return None
    domain, _, service = domain_service.partition(".")
    if not domain or not service:
        return None
    data: dict[str, Any] = {}
    for pair in parts[1:]:
        if "=" not in pair:
            continue
        key, _, val = pair.partition("=")
        key = key.strip().lower()
        val = val.strip()
        if not key:
            continue
        # Type coercion for common params
        if key in ("brightness", "color_temp_kelvin"):
            try:
                data[key] = int(val)
            except ValueError:
                continue
        elif key == "transition":
            try:
                data[key] = float(val)
            except ValueError:
                continue
        elif key == "rgb_color":
            try:
                rgb = [int(x.strip()) for x in val.split(",")]
                if len(rgb) == 3 and all(0 <= x <= 255 for x in rgb):
                    data[key] = rgb
            except (ValueError, AttributeError):
                continue
        else:
            data[key] = val
    return domain, service, data

async def list_entities(
    base_url: str,
    token: str,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """List all entities, optionally filtered by domain.

    Returns list of dicts with entity_id, state, friendly_name.
    """
    url = f"{base_url.rstrip('/')}/api/states"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("[home_assistant] Unauthorized: check HA_ACCESS_TOKEN")
            return []
        logger.warning("[home_assistant] list_entities failed: %s", e)
        return []
    except httpx.RequestError as e:
        logger.warning("[home_assistant] list_entities connection failed: %s", e)
        return []

    data = resp.json()
    if not isinstance(data, list):
        return []

    entities: list[dict[str, Any]] = []
    for state in data:
        if not isinstance(state, dict):
            continue
        entity_id = state.get("entity_id", "")
        if domain and not entity_id.startswith(f"{domain}."):
            continue
        entities.append({
            "entity_id": entity_id,
            "state": state.get("state", "unknown"),
            "friendly_name": state.get("attributes", {}).get("friendly_name", entity_id),
        })
    return entities


async def find_entities(
    base_url: str,
    token: str,
    query: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search entities by friendly_name or entity_id. Query is split into words; all words must match (case-insensitive).

    Returns list of dicts with entity_id, state, friendly_name, ordered by relevance (friendly_name matches first).
    """
    entities = await list_entities(base_url, token, domain=None)
    if not entities:
        return []

    # Split on spaces and hyphens: "bedroom-master table lamp" -> ["bedroom", "master", "table", "lamp"]
    raw_words = query.strip().split()
    words = []
    for w in raw_words:
        words.extend(part.lower() for part in w.replace("-", " ").split() if part)
    if not words:
        return entities[:max_results]

    def score(e: dict[str, Any]) -> tuple[int, str]:
        """Higher = better. (0, "") = no match."""
        fn = (e.get("friendly_name") or "").lower()
        eid = (e.get("entity_id") or "").lower()
        # All words must appear in friendly_name or entity_id
        for w in words:
            if w not in fn and w not in eid:
                return (0, "")
        # Prefer friendly_name matches (exact phrase in fn scores highest)
        fn_matches = sum(1 for w in words if w in fn)
        eid_matches = sum(1 for w in words if w in eid)
        return (fn_matches * 2 + eid_matches, eid)

    scored = [(score(e), e) for e in entities]
    matched = [e for (s, e) in scored if s[0] > 0]
    matched.sort(key=lambda x: score(x), reverse=True)
    return matched[:max_results]


async def get_state(
    base_url: str,
    token: str,
    entity_id: str,
) -> dict[str, Any] | None:
    """Get current state of an entity. Returns None on connection/auth error; returns dict with 'error' key if entity not found."""
    url = f"{base_url.rstrip('/')}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                return {"entity_id": entity_id, "error": "not found"}
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("[home_assistant] Unauthorized: check HA_ACCESS_TOKEN")
        else:
            logger.warning("[home_assistant] get_state failed for %s: %s", entity_id, e)
        return None
    except httpx.RequestError as e:
        logger.warning("[home_assistant] get_state connection failed for %s: %s", entity_id, e)
        return None

    return resp.json()


def _normalize_service_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize service data for Home Assistant. Some integrations expect entity_id as a list."""
    if not data:
        return {}
    result = dict(data)
    if "entity_id" in result and isinstance(result["entity_id"], str):
        result["entity_id"] = [result["entity_id"]]
    return result


async def call_service(
    base_url: str,
    token: str,
    domain: str,
    service: str,
    data: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Call a Home Assistant service.

    Returns (success, message).
    """
    url = f"{base_url.rstrip('/')}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = _normalize_service_data(data or {})
    logger.debug("[home_assistant] POST %s payload=%s", url, payload)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            logger.debug("[home_assistant] Response %s body=%s", resp.status_code, resp.text[:500] if resp.text else "")
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("[home_assistant] Unauthorized: check HA_ACCESS_TOKEN")
            return False, "Home Assistant: Unauthorized (check access token)"
        logger.warning("[home_assistant] call_service failed: %s", e)
        return False, str(e)
    except httpx.RequestError as e:
        logger.warning("[home_assistant] call_service connection failed: %s", e)
        return False, f"Connection failed: {e}"

    return True, f"Successfully called {domain}.{service}"


def format_ha_context(
    list_results: list[dict],
    state_results: list[dict | None],
    service_results: list[tuple[bool, str]],
    find_results: dict[str, list[dict]] | None = None,
    find_fallbacks: dict[str, list[dict]] | None = None,
) -> str:
    """Format Home Assistant results as context text for the AI.

    find_results: {query: [entities]} from [HA_FIND: query] markers.
    find_fallbacks: when find returns empty, {query: [all lights]} to help user identify the entity.
    """
    parts: list[str] = []
    if find_results:
        for query, entities in find_results.items():
            if entities:
                lines = [
                    f"- {e['entity_id']}: {e['state']} ({e.get('friendly_name', '')})"
                    for e in entities
                ]
                parts.append(f"## Home Assistant search for \"{query}\"\n\n" + "\n".join(lines))
            else:
                fallback = (find_fallbacks or {}).get(query, [])
                if fallback:
                    lines = [
                        f"- {e['entity_id']}: {e.get('friendly_name', '')}"
                        for e in fallback
                    ]
                    parts.append(
                        f"## Home Assistant search for \"{query}\"\n\n"
                        "No matching entities found. All lights in the system:\n\n"
                        + "\n".join(lines)
                    )
                else:
                    parts.append(f"## Home Assistant search for \"{query}\"\n\nNo matching entities found.")
    if list_results:
        lines = []
        for e in list_results:
            lines.append(f"- {e['entity_id']}: {e['state']} ({e.get('friendly_name', '')})")
        parts.append("## Home Assistant entities\n\n" + "\n".join(lines))
    if state_results:
        lines = []
        for s in state_results:
            if s is None:
                continue
            eid = s.get("entity_id", "?")
            if "error" in s:
                lines.append(f"- {eid}: {s['error']} (entity does not exist in Home Assistant)")
                continue
            state = s.get("state", "?")
            attrs = s.get("attributes", {})
            extra = []
            if "unit_of_measurement" in attrs:
                extra.append(f"{attrs['unit_of_measurement']}")
            if "brightness" in attrs:
                pct = round(100 * int(attrs.get("brightness", 0)) / 255)
                extra.append(f"brightness {pct}%")
            if "color_temp_kelvin" in attrs:
                extra.append(f"{attrs['color_temp_kelvin']}K")
            if "rgb_color" in attrs:
                extra.append(f"rgb{attrs['rgb_color']}")
            suffix = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"- {eid}: {state}{suffix}")
        if lines:
            parts.append("## Home Assistant state\n\n" + "\n".join(lines))
    if service_results:
        lines = []
        for ok, msg in service_results:
            status = "OK" if ok else "Error"
            lines.append(f"- [{status}] {msg}")
        parts.append("## Home Assistant service call\n\n" + "\n".join(lines))
    if not parts:
        return ""
    return "\n\n".join(parts)
