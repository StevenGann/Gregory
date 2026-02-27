"""Load memory context for AI chat — mirrors notes/loader.py."""

import logging

from gregory.memory.vector_store import MemoryVectorStore

logger = logging.getLogger(__name__)

# Per-user pending memory search results (from [MEMORY_SEARCH:] markers in the prior turn).
# user_id -> list of result dicts
_pending_results: dict[str, list[dict]] = {}


def set_pending_memory_results(user_id: str, results: list[dict]) -> None:
    """Store memory search results to be injected in the next chat turn."""
    _pending_results[user_id] = results


def pop_pending_memory_results(user_id: str) -> list[dict]:
    """Retrieve and clear pending memory search results for a user."""
    return _pending_results.pop(user_id, [])


async def load_memory_for_chat(
    user_id: str,
    message: str,
    vector_store: MemoryVectorStore,
) -> str:
    """Assemble memory context for a chat turn.

    1. Check for pending [MEMORY_SEARCH:] results from the previous turn.
    2. Run automatic vector similarity search on the user's current message.
    3. Deduplicate and format as Markdown.

    Returns an empty string if no relevant memories are found.
    """
    hits: list[dict] = []

    # 1. Pending explicit search results (shown first, highest priority)
    pending = pop_pending_memory_results(user_id)
    if pending:
        hits.extend(pending)
        logger.debug("[memory] %d pending search results for %s", len(pending), user_id)

    # 2. Automatic similarity search on the current message
    auto_hits = await vector_store.search(query=message)
    existing_texts = {h["text"] for h in hits}
    for h in auto_hits:
        if h["text"] not in existing_texts:
            hits.append(h)
            existing_texts.add(h["text"])

    if not hits:
        return ""

    lines: list[str] = []
    for h in hits:
        meta = h.get("metadata", {})
        entry_date = meta.get("date", "unknown date")
        lines.append(f"[Date: {entry_date}] {h['text']}")

    context = "## Relevant memories\n\n" + "\n".join(lines)
    logger.info("[memory] Injecting %d relevant memories for %s", len(hits), user_id)
    return context
