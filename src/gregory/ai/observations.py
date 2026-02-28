"""Extract and process AI observations and memory markers from chat responses."""

import re
from dataclasses import dataclass

OBSERVATION_PATTERN = re.compile(r"\[OBSERVATION:\s*([^\]]*)\]", re.IGNORECASE)
GREGORY_NOTE_PATTERN = re.compile(r"\[GREGORY_NOTE:\s*([^\]]*)\]", re.IGNORECASE)
HOUSEHOLD_NOTE_PATTERN = re.compile(r"\[HOUSEHOLD_NOTE:\s*([^\]]*)\]", re.IGNORECASE)
# [NOTE:entity_id: content] e.g. [NOTE:dog: loves treats]
ENTITY_NOTE_PATTERN = re.compile(
    r"\[NOTE:\s*([a-zA-Z0-9_-]+):\s*([^\]]*)\]",
    re.IGNORECASE,
)

# Memory system markers
JOURNAL_PATTERN = re.compile(r"\[JOURNAL:\s*([^\]]*)\]", re.IGNORECASE)
MEMORY_SEARCH_PATTERN = re.compile(r"\[MEMORY_SEARCH:\s*([^\]]*)\]", re.IGNORECASE)
WIKIPEDIA_PATTERN = re.compile(r"\[WIKIPEDIA:\s*([^\]]*)\]", re.IGNORECASE)
WEB_SEARCH_PATTERN = re.compile(r"\[WEB_SEARCH:\s*([^\]]*)\]", re.IGNORECASE)

# Home Assistant markers
HA_LIST_PATTERN = re.compile(r"\[HA_LIST(?:\s*:\s*([a-zA-Z0-9_]+))?\]", re.IGNORECASE)
HA_FIND_PATTERN = re.compile(r"\[HA_FIND:\s*([^\]]+)\]", re.IGNORECASE)
HA_STATE_PATTERN = re.compile(r"\[HA_STATE:\s*([^\]]+)\]", re.IGNORECASE)
HA_SERVICE_PATTERN = re.compile(r"\[HA_SERVICE:\s*([^\]]+)\]", re.IGNORECASE)


@dataclass
class Observation:
    """A single observation with target and content."""

    target: str  # "user", "gregory", "household", or entity_id
    content: str


@dataclass
class JournalEntry:
    """A journal entry marker [JOURNAL: text]."""

    content: str


@dataclass
class MemorySearchRequest:
    """A memory search request marker [MEMORY_SEARCH: query]."""

    query: str


@dataclass
class WikipediaSearchRequest:
    """A Wikipedia search request marker [WIKIPEDIA: query]."""

    query: str


@dataclass
class WebSearchRequest:
    """A web search request marker [WEB_SEARCH: query]."""

    query: str


@dataclass
class HAListRequest:
    """List entities marker [HA_LIST] or [HA_LIST: domain]."""

    domain: str | None  # None = all entities


@dataclass
class HAStateRequest:
    """Get state marker [HA_STATE: entity_id]."""

    entity_id: str


@dataclass
class HAServiceRequest:
    """Call service marker [HA_SERVICE: domain.service | key=val | ...]."""

    params_str: str  # raw string for parse_service_params


@dataclass
class HAFindRequest:
    """Find entities by name marker [HA_FIND: query]."""

    query: str


def extract_observations(text: str) -> tuple[str, list[Observation]]:
    """Extract observation blocks from response text.

    [OBSERVATION: x] -> user
    [GREGORY_NOTE: x] -> gregory
    [HOUSEHOLD_NOTE: x] -> household
    [NOTE:entity: x] -> entity

    Returns:
        (cleaned_response, list_of_observations)
    """
    observations: list[Observation] = []

    def repl_obs(m):
        observations.append(Observation("user", m.group(1).strip()))
        return ""

    def repl_gregory(m):
        observations.append(Observation("gregory", m.group(1).strip()))
        return ""

    def repl_household(m):
        observations.append(Observation("household", m.group(1).strip()))
        return ""

    def repl_entity(m):
        observations.append(Observation(m.group(1).strip().lower(), m.group(2).strip()))
        return ""

    cleaned = OBSERVATION_PATTERN.sub(repl_obs, text)
    cleaned = GREGORY_NOTE_PATTERN.sub(repl_gregory, cleaned)
    cleaned = HOUSEHOLD_NOTE_PATTERN.sub(repl_household, cleaned)
    cleaned = ENTITY_NOTE_PATTERN.sub(repl_entity, cleaned)
    return cleaned.strip(), observations


def extract_memory_markers(
    text: str,
) -> tuple[
    str,
    list[JournalEntry],
    list[MemorySearchRequest],
    list[WikipediaSearchRequest],
    list[WebSearchRequest],
    list["HAListRequest"],
    list["HAFindRequest"],
    list["HAStateRequest"],
    list["HAServiceRequest"],
]:
    """Extract [JOURNAL:], [MEMORY_SEARCH:], [WIKIPEDIA:], [WEB_SEARCH:], and HA markers.

    Called before extract_observations so the text passed to observations is
    already stripped of memory markers.

    Returns a 9-tuple:
        (0) cleaned_text: response with all markers removed
        (1) journal_entries: [JOURNAL: text] entries to persist
        (2) memory_search_requests: [MEMORY_SEARCH: query] for deferred injection
        (3) wikipedia_requests: [WIKIPEDIA: query] for immediate tool call
        (4) web_search_requests: [WEB_SEARCH: query] for immediate tool call
        (5) ha_list_requests: [HA_LIST] or [HA_LIST: domain]
        (6) ha_find_requests: [HA_FIND: name]
        (7) ha_state_requests: [HA_STATE: entity_id]
        (8) ha_service_requests: [HA_SERVICE: params]
    """
    journals: list[JournalEntry] = []
    searches: list[MemorySearchRequest] = []
    wiki_searches: list[WikipediaSearchRequest] = []
    web_searches: list[WebSearchRequest] = []
    ha_list_reqs: list[HAListRequest] = []
    ha_find_reqs: list[HAFindRequest] = []
    ha_state_reqs: list[HAStateRequest] = []
    ha_service_reqs: list[HAServiceRequest] = []

    def repl_journal(m: re.Match) -> str:
        content = m.group(1).strip()
        if content:
            journals.append(JournalEntry(content))
        return ""

    def repl_search(m: re.Match) -> str:
        query = m.group(1).strip()
        if query:
            searches.append(MemorySearchRequest(query))
        return ""

    def repl_wikipedia(m: re.Match) -> str:
        query = m.group(1).strip()
        if query:
            wiki_searches.append(WikipediaSearchRequest(query))
        return ""

    def repl_web_search(m: re.Match) -> str:
        query = m.group(1).strip()
        if query:
            web_searches.append(WebSearchRequest(query))
        return ""

    def repl_ha_list(m: re.Match) -> str:
        domain = m.group(1)
        ha_list_reqs.append(HAListRequest(domain=domain.strip() if domain else None))
        return ""

    def repl_ha_find(m: re.Match) -> str:
        query = m.group(1).strip()
        if query:
            ha_find_reqs.append(HAFindRequest(query=query))
        return ""

    def repl_ha_state(m: re.Match) -> str:
        entity_id = m.group(1).strip()
        if entity_id:
            ha_state_reqs.append(HAStateRequest(entity_id=entity_id))
        return ""

    def repl_ha_service(m: re.Match) -> str:
        params = m.group(1).strip()
        if params:
            ha_service_reqs.append(HAServiceRequest(params_str=params))
        return ""

    cleaned = JOURNAL_PATTERN.sub(repl_journal, text)
    cleaned = MEMORY_SEARCH_PATTERN.sub(repl_search, cleaned)
    cleaned = WIKIPEDIA_PATTERN.sub(repl_wikipedia, cleaned)
    cleaned = WEB_SEARCH_PATTERN.sub(repl_web_search, cleaned)
    cleaned = HA_LIST_PATTERN.sub(repl_ha_list, cleaned)
    cleaned = HA_FIND_PATTERN.sub(repl_ha_find, cleaned)
    cleaned = HA_STATE_PATTERN.sub(repl_ha_state, cleaned)
    cleaned = HA_SERVICE_PATTERN.sub(repl_ha_service, cleaned)
    return (
        cleaned.strip(),
        journals,
        searches,
        wiki_searches,
        web_searches,
        ha_list_reqs,
        ha_find_reqs,
        ha_state_reqs,
        ha_service_reqs,
    )
