"""Memory service - coordinates journal writes and vector indexing."""

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from gregory.config import get_settings
from gregory.memory.journal import JournalService
from gregory.memory.vector_store import MemoryVectorStore

logger = logging.getLogger(__name__)

# Module-level singletons — created on first use, shared for the process lifetime.
_journal_svc: JournalService | None = None
_vector_store: MemoryVectorStore | None = None


def get_journal_service() -> JournalService:
    global _journal_svc
    if _journal_svc is None:
        _journal_svc = JournalService()
    return _journal_svc


def get_vector_store() -> MemoryVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = MemoryVectorStore()
    return _vector_store


async def write_journal_entry(
    text: str,
    user_id: str = "",
    for_date: date | None = None,
) -> None:
    """Write a journal entry to disk and immediately index it in the vector DB.

    This is the main write path called after extracting [JOURNAL:] markers from
    an AI response.
    """
    if not text.strip():
        return
    journal = get_journal_service()
    vector = get_vector_store()

    entry_date, entry_line = journal.append_entry(
        text=text, user_id=user_id, for_date=for_date
    )

    # Unique ID: date + millisecond timestamp
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    doc_id = f"{entry_date.isoformat()}::{ts_ms}"

    await vector.index_entry(
        doc_id=doc_id,
        text=entry_line,
        entry_date=entry_date,
        user_id=user_id,
        entry_type="entry",
    )
    logger.info("[memory] Journal entry written and indexed for %s", entry_date)


async def startup_reindex() -> None:
    """Called at app startup when memory_enabled=True.

    Rebuilds the vector index from all existing journal and compressed monthly
    files. Idempotent — safe to run on every startup.
    """
    journal = get_journal_service()
    vector = get_vector_store()
    await vector.reindex_all(journal)
