"""Notes service - per-user and household Markdown notes."""

from gregory.notes.service import NotesService
from gregory.notes.loader import load_notes_for_chat

__all__ = ["NotesService", "load_notes_for_chat"]
