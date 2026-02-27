"""Tests for observation and memory marker extraction (ai/observations.py)."""

import pytest

from gregory.ai.observations import (
    JournalEntry,
    MemorySearchRequest,
    Observation,
    extract_memory_markers,
    extract_observations,
)


# ---------------------------------------------------------------------------
# extract_memory_markers — [JOURNAL:] marker
# ---------------------------------------------------------------------------

def test_extract_memory_markers_journal_single():
    text = "Sure! [JOURNAL: We discussed the garden plans today.]"
    cleaned, journals, searches = extract_memory_markers(text)
    assert len(journals) == 1
    assert journals[0].content == "We discussed the garden plans today."
    assert "[JOURNAL:" not in cleaned


def test_extract_memory_markers_journal_stripped_from_response():
    text = "Here is my answer. [JOURNAL: Some event.] Hope that helps!"
    cleaned, journals, _ = extract_memory_markers(text)
    assert "Some event." not in cleaned
    assert "Here is my answer." in cleaned
    assert "Hope that helps!" in cleaned


def test_extract_memory_markers_journal_multiple():
    text = "[JOURNAL: First thing.] ... [JOURNAL: Second thing.]"
    _, journals, _ = extract_memory_markers(text)
    assert len(journals) == 2
    assert journals[0].content == "First thing."
    assert journals[1].content == "Second thing."


def test_extract_memory_markers_journal_case_insensitive():
    text = "[journal: lowercase marker]"
    _, journals, _ = extract_memory_markers(text)
    assert len(journals) == 1
    assert journals[0].content == "lowercase marker"


def test_extract_memory_markers_journal_empty_content_ignored():
    text = "[JOURNAL: ] some text"
    _, journals, _ = extract_memory_markers(text)
    assert len(journals) == 0


# ---------------------------------------------------------------------------
# extract_memory_markers — [MEMORY_SEARCH:] marker
# ---------------------------------------------------------------------------

def test_extract_memory_markers_search_single():
    text = "Let me check that. [MEMORY_SEARCH: dishwasher repair]"
    cleaned, _, searches = extract_memory_markers(text)
    assert len(searches) == 1
    assert searches[0].query == "dishwasher repair"
    assert "[MEMORY_SEARCH:" not in cleaned


def test_extract_memory_markers_search_multiple():
    text = "[MEMORY_SEARCH: first query] text [MEMORY_SEARCH: second query]"
    _, _, searches = extract_memory_markers(text)
    assert len(searches) == 2
    assert searches[0].query == "first query"
    assert searches[1].query == "second query"


def test_extract_memory_markers_search_empty_query_ignored():
    text = "[MEMORY_SEARCH: ]"
    _, _, searches = extract_memory_markers(text)
    assert len(searches) == 0


# ---------------------------------------------------------------------------
# extract_memory_markers — mixed with observations
# ---------------------------------------------------------------------------

def test_extract_memory_markers_coexists_with_observations():
    """Memory markers and observation markers can appear in the same response."""
    text = (
        "Here's my answer. "
        "[JOURNAL: We talked about Alice's birthday.] "
        "[OBSERVATION: Alice's birthday is in March.] "
        "[MEMORY_SEARCH: past birthdays]"
    )
    cleaned, journals, searches = extract_memory_markers(text)
    # Memory markers stripped
    assert len(journals) == 1
    assert len(searches) == 1
    # Observation marker NOT stripped by extract_memory_markers (different function)
    assert "[OBSERVATION:" in cleaned


def test_extract_memory_markers_then_observations():
    """Full pipeline: extract_memory_markers first, then extract_observations."""
    text = (
        "Response. "
        "[JOURNAL: important event] "
        "[OBSERVATION: user likes tea]"
    )
    cleaned, journals, _ = extract_memory_markers(text)
    cleaned2, observations = extract_observations(cleaned)
    assert journals[0].content == "important event"
    assert observations[0].content == "user likes tea"
    assert "[JOURNAL:" not in cleaned2
    assert "[OBSERVATION:" not in cleaned2


# ---------------------------------------------------------------------------
# Regression: existing extract_observations still works unchanged
# ---------------------------------------------------------------------------

def test_extract_observations_user():
    text = "Sure! [OBSERVATION: Alice prefers morning reminders]"
    cleaned, obs = extract_observations(text)
    assert len(obs) == 1
    assert obs[0].target == "user"
    assert obs[0].content == "Alice prefers morning reminders"
    assert "[OBSERVATION:" not in cleaned


def test_extract_observations_gregory_note():
    text = "[GREGORY_NOTE: I should be more concise]"
    _, obs = extract_observations(text)
    assert obs[0].target == "gregory"


def test_extract_observations_household_note():
    text = "[HOUSEHOLD_NOTE: Trash day is Tuesday]"
    _, obs = extract_observations(text)
    assert obs[0].target == "household"


def test_extract_observations_entity_note():
    text = "[NOTE:dog: loves bacon treats]"
    _, obs = extract_observations(text)
    assert obs[0].target == "dog"
    assert obs[0].content == "loves bacon treats"


def test_extract_observations_multiple():
    text = (
        "Done. [OBSERVATION: Alice hates spiders] "
        "[HOUSEHOLD_NOTE: Boiler needs servicing] "
        "[NOTE:cat: indoor only]"
    )
    cleaned, obs = extract_observations(text)
    assert len(obs) == 3
    assert "[OBSERVATION:" not in cleaned
    assert "[HOUSEHOLD_NOTE:" not in cleaned
    assert "[NOTE:" not in cleaned


def test_extract_observations_no_markers():
    text = "Just a regular response with no markers."
    cleaned, obs = extract_observations(text)
    assert cleaned == text
    assert obs == []
