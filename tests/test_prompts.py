"""Tests for system prompt building (ai/prompts.py)."""

import pytest

from gregory.ai.prompts import (
    DEFAULT_SYSTEM_PROMPT,
    JOURNAL_INSTRUCTION,
    MEMORY_SEARCH_INSTRUCTION,
    OBSERVATION_INSTRUCTION,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# Baseline behaviour (backwards compatibility)
# ---------------------------------------------------------------------------

def test_build_system_prompt_minimal():
    result = build_system_prompt("")
    assert DEFAULT_SYSTEM_PROMPT.strip() in result


def test_build_system_prompt_with_notes():
    result = build_system_prompt("## Household notes\nTrash day is Tuesday.")
    assert "Trash day is Tuesday." in result
    assert "## Your knowledge (from notes)" in result


def test_build_system_prompt_no_notes_no_knowledge_header():
    result = build_system_prompt("")
    assert "## Your knowledge" not in result


def test_build_system_prompt_with_user_id():
    result = build_system_prompt("", user_id="alice")
    assert "alice" in result
    assert "## Current conversation" in result


def test_build_system_prompt_observations_enabled():
    result = build_system_prompt("", observations_enabled=True)
    assert "[OBSERVATION:" in result
    assert OBSERVATION_INSTRUCTION.strip() in result


def test_build_system_prompt_observations_disabled():
    result = build_system_prompt("")
    assert "[OBSERVATION:" not in result


# ---------------------------------------------------------------------------
# Memory context injection
# ---------------------------------------------------------------------------

def test_build_system_prompt_with_memory_context():
    memory_ctx = "## Relevant memories\n\n[Date: 2024-01-10] Alice has a shellfish allergy."
    result = build_system_prompt("", memory_context=memory_ctx)
    assert "Alice has a shellfish allergy." in result
    assert "## Relevant memories" in result


def test_build_system_prompt_empty_memory_context_not_injected():
    result = build_system_prompt("")
    assert "## Relevant memories" not in result


def test_build_system_prompt_memory_context_appears_before_notes():
    memory_ctx = "## Relevant memories\n\n[Date: 2024-01-01] Something."
    notes_ctx = "## Household notes\nSomething else."
    result = build_system_prompt(notes_ctx, memory_context=memory_ctx)
    mem_pos = result.index("Relevant memories")
    notes_pos = result.index("Household notes")
    assert mem_pos < notes_pos


# ---------------------------------------------------------------------------
# Memory instructions
# ---------------------------------------------------------------------------

def test_build_system_prompt_memory_enabled_adds_journal_instruction():
    result = build_system_prompt("", memory_enabled=True)
    assert "[JOURNAL:" in result
    assert JOURNAL_INSTRUCTION.strip() in result


def test_build_system_prompt_memory_enabled_adds_search_instruction():
    result = build_system_prompt("", memory_enabled=True)
    assert "[MEMORY_SEARCH:" in result
    assert MEMORY_SEARCH_INSTRUCTION.strip() in result


def test_build_system_prompt_memory_disabled_no_journal_instruction():
    result = build_system_prompt("", memory_enabled=False)
    assert "[JOURNAL:" not in result
    assert "[MEMORY_SEARCH:" not in result


# ---------------------------------------------------------------------------
# Combined flags
# ---------------------------------------------------------------------------

def test_build_system_prompt_all_features_enabled():
    result = build_system_prompt(
        "## Household notes\nFacts here.",
        observations_enabled=True,
        user_id="bob",
        memory_context="## Relevant memories\n\n[Date: 2024-01-01] Something.",
        memory_enabled=True,
    )
    assert "bob" in result
    assert "Facts here." in result
    assert "Relevant memories" in result
    assert "[OBSERVATION:" in result
    assert "[JOURNAL:" in result
    assert "[MEMORY_SEARCH:" in result


def test_build_system_prompt_returns_string():
    result = build_system_prompt("some notes")
    assert isinstance(result, str)
    assert len(result) > 0
