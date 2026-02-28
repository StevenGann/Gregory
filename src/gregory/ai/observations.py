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
]:
    """Extract [JOURNAL:], [MEMORY_SEARCH:], [WIKIPEDIA:], and [WEB_SEARCH:] markers.

    Called before extract_observations so the text passed to the existing
    function is already stripped of memory markers.

    Returns:
        (cleaned_text, journal_entries, memory_search_requests, wikipedia_requests, web_search_requests)
    """
    journals: list[JournalEntry] = []
    searches: list[MemorySearchRequest] = []
    wiki_searches: list[WikipediaSearchRequest] = []
    web_searches: list[WebSearchRequest] = []

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

    cleaned = JOURNAL_PATTERN.sub(repl_journal, text)
    cleaned = MEMORY_SEARCH_PATTERN.sub(repl_search, cleaned)
    cleaned = WIKIPEDIA_PATTERN.sub(repl_wikipedia, cleaned)
    cleaned = WEB_SEARCH_PATTERN.sub(repl_web_search, cleaned)
    return cleaned.strip(), journals, searches, wiki_searches, web_searches
