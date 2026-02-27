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
    """
    Run heartbeat tasks. Starts reflection and notes-cleanup loops in parallel.
    Exits when both intervals are 0 (disabled).
    """
    settings = get_settings()
    reflection_m = getattr(settings, "heartbeat_reflection_minutes", 0) or 0
    cleanup_m = getattr(settings, "heartbeat_notes_cleanup_minutes", 0) or 0

    if reflection_m <= 0 and cleanup_m <= 0:
        logger.info("[heartbeat] Both intervals disabled, heartbeat not started")
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

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        raise
