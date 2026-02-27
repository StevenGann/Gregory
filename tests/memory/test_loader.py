"""Tests for memory loader (memory/loader.py)."""

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gregory.memory.loader import (
    load_memory_for_chat,
    pop_pending_memory_results,
    set_pending_memory_results,
)


def _make_hit(text: str, entry_date: str = "2024-01-15", similarity: float = 0.9) -> dict:
    return {"text": text, "metadata": {"date": entry_date, "user_id": ""}, "similarity": similarity}


# ---------------------------------------------------------------------------
# Pending results mechanism
# ---------------------------------------------------------------------------

def test_set_and_pop_pending_results():
    hits = [_make_hit("some memory")]
    set_pending_memory_results("alice", hits)
    result = pop_pending_memory_results("alice")
    assert result == hits


def test_pop_clears_pending_results():
    set_pending_memory_results("bob", [_make_hit("mem")])
    pop_pending_memory_results("bob")
    # Second pop should return empty
    assert pop_pending_memory_results("bob") == []


def test_pop_returns_empty_for_unknown_user():
    assert pop_pending_memory_results("nonexistent_user_xyz") == []


def test_pending_results_are_user_scoped():
    set_pending_memory_results("alice", [_make_hit("alice memory")])
    set_pending_memory_results("bob", [_make_hit("bob memory")])
    assert pop_pending_memory_results("alice")[0]["text"] == "alice memory"
    assert pop_pending_memory_results("bob")[0]["text"] == "bob memory"


# ---------------------------------------------------------------------------
# load_memory_for_chat
# ---------------------------------------------------------------------------

async def test_load_memory_for_chat_empty_returns_empty():
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])
    result = await load_memory_for_chat("alice", "hello", mock_store)
    assert result == ""


async def test_load_memory_for_chat_formats_hits():
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        _make_hit("Alice is allergic to shellfish", "2024-01-10"),
    ])
    result = await load_memory_for_chat("alice", "what are alice's allergies?", mock_store)
    assert "## Relevant memories" in result
    assert "2024-01-10" in result
    assert "Alice is allergic to shellfish" in result


async def test_load_memory_for_chat_includes_multiple_hits():
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[
        _make_hit("memory one", "2024-01-01"),
        _make_hit("memory two", "2024-01-02"),
    ])
    result = await load_memory_for_chat("alice", "what happened?", mock_store)
    assert "memory one" in result
    assert "memory two" in result


async def test_load_memory_injects_pending_results_first():
    """Pending results from [MEMORY_SEARCH:] should appear before auto-search results."""
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[_make_hit("auto result")])

    set_pending_memory_results("alice", [_make_hit("pending result", "2024-01-01")])
    result = await load_memory_for_chat("alice", "some query", mock_store)

    assert "pending result" in result
    assert "auto result" in result
    # Pending result should appear before auto result in the output
    assert result.index("pending result") < result.index("auto result")


async def test_load_memory_deduplicates_results():
    """A result from pending should not appear again from auto-search."""
    duplicate_text = "shared memory text"
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[_make_hit(duplicate_text)])

    set_pending_memory_results("alice", [_make_hit(duplicate_text)])
    result = await load_memory_for_chat("alice", "query", mock_store)

    # Should only appear once
    assert result.count(duplicate_text) == 1


async def test_load_memory_clears_pending_after_use():
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])

    set_pending_memory_results("alice", [_make_hit("pending")])
    await load_memory_for_chat("alice", "query", mock_store)

    # Second call — pending should be empty now
    result = await load_memory_for_chat("alice", "query", mock_store)
    assert "pending" not in result


async def test_load_memory_calls_search_with_message(fake_settings):
    """The vector store should be searched with the user's exact message."""
    mock_store = MagicMock()
    mock_store.search = AsyncMock(return_value=[])
    await load_memory_for_chat("alice", "what happened with the boiler?", mock_store)
    mock_store.search.assert_awaited_once()
    call_kwargs = mock_store.search.await_args
    assert "what happened with the boiler?" in str(call_kwargs)
