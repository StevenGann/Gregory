"""In-memory conversation history store. Per-user, single conversation each.

Each user has a single ongoing conversation. History is held in memory only —
it is lost when the Gregory process restarts. This is an intentional design
choice for Phase 1: simplicity over persistence. Future phases may add
database-backed persistence.

The store is module-level (process-global) so it is shared across all request
handlers within the same server process.
"""

from collections import defaultdict
from datetime import datetime

from gregory.ai.providers.base import ChatMessage

# user_id -> list of ChatMessage (all messages for this user's session)
_history: dict[str, list[ChatMessage]] = defaultdict(list)

# user_id -> conversation_id (stable UUID-like string for the lifetime of the process)
_conversation_ids: dict[str, str] = {}

# Simple incrementing counter used to generate unique conversation IDs
_id_counter = 0


def _next_id() -> str:
    """Generate the next sequential conversation ID (e.g. 'conv_1', 'conv_2')."""
    global _id_counter
    _id_counter += 1
    return f"conv_{_id_counter}"


def get_conversation_id(user_id: str) -> str:
    """Get or create a stable conversation ID for the user."""
    if user_id not in _conversation_ids:
        _conversation_ids[user_id] = _next_id()
    return _conversation_ids[user_id]


def get_history(user_id: str) -> list[ChatMessage]:
    """Get conversation history for a user (last N messages)."""
    hist = _history[user_id]
    # Limit to last 20 turns (40 messages) for context window
    max_messages = 40
    if len(hist) <= max_messages:
        return hist.copy()
    return hist[-max_messages:].copy()


def append(user_id: str, role: str, content: str, timestamp: datetime | None = None) -> None:
    """Append a message to the user's conversation."""
    ts = timestamp if timestamp is not None else datetime.now()
    _history[user_id].append(ChatMessage(role=role, content=content, timestamp=ts))
