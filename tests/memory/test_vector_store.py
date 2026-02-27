"""Tests for MemoryVectorStore (memory/vector_store.py)."""

from datetime import date
from pathlib import Path

import pytest

from gregory.memory.vector_store import MemoryVectorStore


@pytest.fixture()
def store(tmp_path: Path, mock_chroma, fake_settings) -> MemoryVectorStore:
    """A MemoryVectorStore backed by an in-memory EphemeralClient."""
    return MemoryVectorStore(memory_path=tmp_path)


# ---------------------------------------------------------------------------
# Basic indexing and search
# ---------------------------------------------------------------------------

async def test_search_empty_collection_returns_empty(store: MemoryVectorStore):
    results = await store.search("anything", n_results=5, threshold=0.0)
    assert results == []


async def test_index_and_search_finds_entry(store: MemoryVectorStore):
    d = date(2024, 1, 15)
    await store.index_entry("2024-01-15::1000", "cats like fish", d)
    # Same text query → cosine similarity 1.0
    results = await store.search("cats like fish", n_results=5, threshold=0.0)
    assert len(results) == 1
    assert results[0]["text"] == "cats like fish"


async def test_search_returns_metadata(store: MemoryVectorStore):
    d = date(2024, 3, 20)
    await store.index_entry("2024-03-20::1000", "rainy day", d, user_id="alice", entry_type="entry")
    results = await store.search("rainy day", n_results=5, threshold=0.0)
    meta = results[0]["metadata"]
    assert meta["date"] == "2024-03-20"
    assert meta["user_id"] == "alice"
    assert meta["type"] == "entry"


async def test_search_returns_similarity_score(store: MemoryVectorStore):
    d = date(2024, 1, 1)
    await store.index_entry("id1", "the quick brown fox", d)
    results = await store.search("the quick brown fox", n_results=1, threshold=0.0)
    assert "similarity" in results[0]
    assert 0.0 <= results[0]["similarity"] <= 1.0


async def test_search_threshold_filters_low_similarity(store: MemoryVectorStore):
    # Index two distinct texts (FakeEF gives them orthogonal embeddings → similarity ≈ 0)
    d = date(2024, 1, 1)
    await store.index_entry("id1", "text about quantum physics", d)
    await store.index_entry("id2", "text about cat food", d)
    # Query for exact first text at high threshold → should return that entry
    # but not the other (similarity ≈ 0 for different texts)
    results = await store.search("text about quantum physics", n_results=5, threshold=0.95)
    texts = [r["text"] for r in results]
    assert "text about quantum physics" in texts
    assert "text about cat food" not in texts


async def test_search_threshold_zero_returns_all(store: MemoryVectorStore):
    d = date(2024, 2, 1)
    await store.index_entry("id1", "entry alpha", d)
    await store.index_entry("id2", "entry beta", d)
    results = await store.search("query", n_results=10, threshold=0.0)
    assert len(results) == 2


async def test_search_respects_n_results_limit(store: MemoryVectorStore):
    d = date(2024, 2, 1)
    for i in range(5):
        await store.index_entry(f"id{i}", f"entry number {i}", d)
    results = await store.search("entry", n_results=2, threshold=0.0)
    assert len(results) <= 2


async def test_search_n_results_capped_at_collection_size(store: MemoryVectorStore):
    """Requesting more results than exist should not raise."""
    d = date(2024, 1, 1)
    await store.index_entry("id1", "only one entry", d)
    # Requesting 10 from a collection of 1 must not raise
    results = await store.search("only one entry", n_results=10, threshold=0.0)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Upsert idempotency
# ---------------------------------------------------------------------------

async def test_upsert_is_idempotent(store: MemoryVectorStore):
    d = date(2024, 1, 15)
    await store.index_entry("same-id", "same text", d)
    await store.index_entry("same-id", "same text", d)
    # Upsert should not duplicate the entry
    results = await store.search("same text", n_results=10, threshold=0.0)
    # Should be exactly one result for this text
    assert sum(1 for r in results if r["text"] == "same text") == 1


# ---------------------------------------------------------------------------
# delete_entries_for_month
# ---------------------------------------------------------------------------

async def test_delete_entries_for_month(store: MemoryVectorStore):
    jan = date(2024, 1, 15)
    feb = date(2024, 2, 10)
    await store.index_entry("jan::1", "january entry", jan)
    await store.index_entry("feb::1", "february entry", feb)

    await store.delete_entries_for_month(2024, 1)

    # January entry gone, February entry still present
    jan_results = await store.search("january entry", n_results=5, threshold=0.95)
    feb_results = await store.search("february entry", n_results=5, threshold=0.95)
    assert len(jan_results) == 0
    assert len(feb_results) == 1


async def test_delete_entries_for_month_noop_when_empty(store: MemoryVectorStore):
    """Should not raise when the month has no entries."""
    await store.delete_entries_for_month(2020, 6)  # no entries for this month


# ---------------------------------------------------------------------------
# index_compressed_month
# ---------------------------------------------------------------------------

async def test_index_compressed_month(store: MemoryVectorStore):
    await store.index_compressed_month(2024, 2, "February summary text")
    results = await store.search("February summary text", n_results=5, threshold=0.0)
    assert len(results) == 1
    assert results[0]["metadata"]["type"] == "compressed"
    assert results[0]["metadata"]["date"] == "2024-02-01"


# ---------------------------------------------------------------------------
# reindex_all
# ---------------------------------------------------------------------------

async def test_reindex_all_indexes_daily_files(store: MemoryVectorStore, tmp_path: Path):
    from gregory.memory.journal import JournalService

    journal = JournalService(memory_path=tmp_path)
    d = date(2024, 1, 20)
    journal.append_entry("an important event", for_date=d)

    await store.reindex_all(journal)

    results = await store.search("- [", n_results=5, threshold=0.0)
    # At least one result was indexed from the journal file
    assert len(results) >= 1


async def test_reindex_all_indexes_compressed_files(store: MemoryVectorStore, tmp_path: Path):
    from gregory.memory.journal import JournalService

    journal = JournalService(memory_path=tmp_path)
    journal.write_compressed(2024, 1, "# January 2024\n\nCompressed month summary.")

    await store.reindex_all(journal)

    results = await store.search("Compressed month summary", n_results=5, threshold=0.0)
    assert len(results) >= 1


async def test_reindex_all_is_idempotent(store: MemoryVectorStore, tmp_path: Path):
    from gregory.memory.journal import JournalService

    journal = JournalService(memory_path=tmp_path)
    journal.append_entry("repeated reindex", for_date=date(2024, 3, 1))

    await store.reindex_all(journal)
    await store.reindex_all(journal)  # Should not raise or duplicate
