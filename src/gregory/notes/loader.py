"""Load notes as context for AI chat."""

from gregory.config import get_settings
from gregory.notes.service import NotesService


def load_notes_for_chat(user_id: str) -> str:
    """Load household + user notes as context string for chat."""
    notes = NotesService()
    household = notes.read_household()
    user = notes.read_user(user_id)

    parts: list[str] = []
    if household:
        parts.append("## Household notes\n" + household.strip())
    if user:
        parts.append(f"## Notes about {user_id}\n" + user.strip())
    if not parts:
        return ""
    return "\n\n".join(parts)
