"""Heartbeat: periodic self-reflection and notes cleanup tasks."""

import asyncio
import logging
import random

from gregory.ai.config import resolve_providers_ordered
from gregory.ai.prompts import (
    HEARTBEAT_NOTES_CLEANUP_SYSTEM,
    HEARTBEAT_REFLECTION_ANSWER_SYSTEM,
    HEARTBEAT_REFLECTION_QUESTION,
)
from gregory.ai.router import _instantiate
from gregory.config import get_settings
from gregory.notes.loader import load_all_notes
from gregory.notes.service import NotesService

logger = logging.getLogger(__name__)


def _get_provider_for_reflection():
    """First available provider for reflection (normal order)."""
    resolved = resolve_providers_ordered()
    for r in resolved:
        p = _instantiate(r)
        if p is not None:
            return p, r.display_name
    return None, None


def _get_provider_for_cleanup():
    """Premium provider for cleanup: last in order (typically Claude/Gemini)."""
    resolved = resolve_providers_ordered()
    for r in reversed(resolved):
        p = _instantiate(r)
        if p is not None:
            return p, r.display_name
    return None, None


async def _run_reflection() -> None:
    """Generate a self-reflection question, answer it, append to gregory.md."""
    provider, name = _get_provider_for_reflection()
    if provider is None:
        logger.warning("[heartbeat] No provider for reflection, skipping")
        return

    notes_svc = NotesService()
    all_notes = load_all_notes()

    try:
        # 1. Generate question
        question_response = await provider.generate(
            prompt=HEARTBEAT_REFLECTION_QUESTION,
            history=[],
            system_context="",
        )
        question = question_response.strip().strip('"\'')
        if not question:
            logger.warning("[heartbeat] Empty reflection question, skipping")
            return

        logger.info("[heartbeat] Reflection question: %s", question[:80])

        # 2. Answer using Gregory's notes
        answer = await provider.generate(
            prompt=f"Reflection question: {question}",
            history=[],
            system_context=f"{HEARTBEAT_REFLECTION_ANSWER_SYSTEM}\n\n## Your notes\n{all_notes or '(none yet)'}",
        )
        answer = answer.strip()
        if not answer:
            logger.warning("[heartbeat] Empty reflection answer, skipping")
            return

        # 3. Append to gregory.md
        line = f"- Reflection on \"{question[:60]}{'...' if len(question) > 60 else ''}\": {answer}"
        notes_svc.append_gregory(line)
        logger.info("[heartbeat] Appended reflection to gregory.md via %s", name)
    except Exception as e:
        logger.exception("[heartbeat] Reflection failed: %s", e)


async def _run_notes_cleanup() -> None:
    """Pick a random note document, summarize/clean it with premium model."""
    provider, name = _get_provider_for_cleanup()
    if provider is None:
        logger.warning("[heartbeat] No provider for notes cleanup, skipping")
        return

    notes_svc = NotesService()
    docs = notes_svc.list_note_documents()
    if not docs:
        logger.info("[heartbeat] No note documents to clean up, skipping")
        return

    doc_type, doc_id = random.choice(docs)
    content = notes_svc.read_document(doc_type, doc_id)
    if not content.strip():
        return

    try:
        cleaned = await provider.generate(
            prompt=f"Clean up these notes:\n\n{content}",
            history=[],
            system_context=HEARTBEAT_NOTES_CLEANUP_SYSTEM,
        )
        cleaned = cleaned.strip()
        if cleaned:
            notes_svc.write_document(doc_type, doc_id, cleaned)
            logger.info("[heartbeat] Cleaned %s/%s via %s", doc_type, doc_id, name)
        else:
            logger.warning("[heartbeat] Empty cleanup output for %s/%s", doc_type, doc_id)
    except Exception as e:
        logger.exception("[heartbeat] Notes cleanup failed for %s/%s: %s", doc_type, doc_id, e)


async def _run_daily_summary() -> None:
    """Generate a daily summary of today's journal entries and write it back to the journal."""
    settings = get_settings()
    if not getattr(settings, "memory_enabled", False):
        return

    from datetime import date, datetime, timezone

    from gregory.memory.service import get_journal_service, get_vector_store

    provider, name = _get_provider_for_reflection()
    if provider is None:
        logger.warning("[heartbeat] No provider for daily summary, skipping")
        return

    journal = get_journal_service()
    today_content = journal.read_today()
    if not today_content.strip():
        logger.info("[heartbeat] Daily summary: no journal entries for today, skipping")
        return
    if "## Summary" in today_content:
        logger.info("[heartbeat] Daily summary: summary already exists for today, skipping")
        return

    try:
        summary = await provider.generate(
            prompt=f"Summarize today's journal entries in 2-3 sentences:\n\n{today_content}",
            history=[],
            system_context=(
                "You are Gregory, a house AI. Summarize your journal entries "
                "concisely in first person, capturing the key events and observations."
            ),
        )
        summary = summary.strip()
        if not summary:
            logger.warning("[heartbeat] Empty daily summary response, skipping")
            return

        today = date.today()
        journal.write_summary(today, summary)

        # Index the summary entry
        ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        doc_id = f"{today.isoformat()}::summary::{ts_ms}"
        vector = get_vector_store()
        await vector.index_entry(
            doc_id=doc_id,
            text=summary,
            entry_date=today,
            user_id="",
            entry_type="summary",
        )
        logger.info("[heartbeat] Daily summary written and indexed via %s", name)
    except Exception as e:
        logger.exception("[heartbeat] Daily summary failed: %s", e)


async def _run_memory_compression() -> None:
    """Compress completed months' daily journal files into a single YYYY-MM.md."""
    settings = get_settings()
    if not getattr(settings, "memory_enabled", False):
        return

    from gregory.memory.service import get_journal_service, get_vector_store

    provider, name = _get_provider_for_cleanup()
    if provider is None:
        logger.warning("[heartbeat] No provider for memory compression, skipping")
        return

    journal = get_journal_service()
    vector = get_vector_store()
    months = journal.list_months_with_daily_files()

    if not months:
        logger.info("[heartbeat] Memory compression: no complete months to compress")
        return

    for year, month in months:
        # Skip if already compressed
        if journal.compressed_path(year, month).exists():
            logger.debug("[heartbeat] Compression: %04d-%02d already compressed, skipping", year, month)
            continue

        raw_content = journal.read_month(year, month)
        if not raw_content.strip():
            continue

        logger.info("[heartbeat] Compressing journal for %04d-%02d", year, month)
        try:
            summary = await provider.generate(
                prompt=(
                    f"Compress this monthly journal into a concise Markdown document "
                    f"preserving all important facts, events, and observations. "
                    f"Use topic headers. Output only the Markdown:\n\n{raw_content}"
                ),
                history=[],
                system_context=(
                    "You are Gregory, a house AI. Create a well-structured monthly "
                    "summary that preserves all meaningful information from the daily entries."
                ),
            )
            summary = summary.strip()
            if not summary:
                logger.warning("[heartbeat] Empty compression output for %04d-%02d, skipping", year, month)
                continue

            # Write compressed file
            header = f"# {year:04d}-{month:02d}\n\n"
            journal.write_compressed(year, month, header + summary)

            # Update vector index: remove daily entries, add compressed summary
            await vector.delete_entries_for_month(year, month)
            await vector.index_compressed_month(year, month, summary)

            # Delete daily files
            deleted = journal.delete_daily_files_for_month(year, month)
            logger.info(
                "[heartbeat] Compressed %04d-%02d (%d daily files deleted) via %s",
                year,
                month,
                len(deleted),
                name,
            )
        except Exception as e:
            logger.exception("[heartbeat] Compression failed for %04d-%02d: %s", year, month, e)


async def _run_periodic(
    name: str,
    interval_minutes: float,
    coro_fn,
) -> None:
    """Run a coroutine periodically."""
    interval_seconds = max(60, interval_minutes * 60)  # Min 1 minute
    while True:
        try:
            await coro_fn()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("[heartbeat] %s task failed: %s", name, e)
        await asyncio.sleep(interval_seconds)


async def run_heartbeat() -> None:
    """Run heartbeat tasks in parallel.

    Tasks:
    - reflection: self-reflection question → answer → gregory.md
    - notes-cleanup: random note document cleaned by premium model
    - daily-summary: today's journal entries summarized (memory system)
    - memory-compression: completed months compressed into YYYY-MM.md
    """
    settings = get_settings()
    reflection_m = getattr(settings, "heartbeat_reflection_minutes", 0) or 0
    cleanup_m = getattr(settings, "heartbeat_notes_cleanup_minutes", 0) or 0
    summary_m = getattr(settings, "heartbeat_daily_summary_minutes", 0) or 0
    compression_m = getattr(settings, "heartbeat_memory_compression_minutes", 0) or 0

    if reflection_m <= 0 and cleanup_m <= 0 and summary_m <= 0 and compression_m <= 0:
        logger.info("[heartbeat] All intervals disabled, heartbeat not started")
        return

    tasks: list[asyncio.Task] = []
    if reflection_m > 0:
        t = asyncio.create_task(
            _run_periodic("reflection", reflection_m, _run_reflection),
            name="heartbeat-reflection",
        )
        tasks.append(t)
        logger.info("[heartbeat] Reflection every %.0f min", reflection_m)
    if cleanup_m > 0:
        t = asyncio.create_task(
            _run_periodic("notes-cleanup", cleanup_m, _run_notes_cleanup),
            name="heartbeat-cleanup",
        )
        tasks.append(t)
        logger.info("[heartbeat] Notes cleanup every %.0f min", cleanup_m)
    if summary_m > 0:
        t = asyncio.create_task(
            _run_periodic("daily-summary", summary_m, _run_daily_summary),
            name="heartbeat-daily-summary",
        )
        tasks.append(t)
        logger.info("[heartbeat] Daily summary every %.0f min", summary_m)
    if compression_m > 0:
        t = asyncio.create_task(
            _run_periodic("memory-compression", compression_m, _run_memory_compression),
            name="heartbeat-memory-compression",
        )
        tasks.append(t)
        logger.info("[heartbeat] Memory compression every %.0f min", compression_m)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        raise
