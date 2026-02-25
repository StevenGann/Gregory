"""Notes service - read/write Markdown notes per user and household."""

import logging
from pathlib import Path

from gregory.config import get_settings

logger = logging.getLogger(__name__)

HOUSEHOLD_FILE = "household.md"


class NotesService:
    """Read and write Markdown notes for household and per-user context."""

    def __init__(self, notes_path: Path | None = None) -> None:
        path = notes_path or get_settings().notes_path
        self._base = Path(path)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        """Path to user notes file (sanitized)."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id.lower())
        return self._base / f"{safe}.md"

    def _household_path(self) -> Path:
        """Path to household notes."""
        return self._base / HOUSEHOLD_FILE

    def read_household(self) -> str:
        """Read household-level notes."""
        p = self._household_path()
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read household notes: %s", e)
            return ""

    def read_user(self, user_id: str) -> str:
        """Read notes for a specific user."""
        p = self._path(user_id)
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read notes for %s: %s", user_id, e)
            return ""

    def append_user(self, user_id: str, content: str) -> None:
        """Append a line or block to user notes."""
        p = self._path(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        line = content.strip()
        if not line.endswith("\n"):
            line += "\n"
        try:
            with p.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Could not append to notes for %s: %s", user_id, e)

    def append_household(self, content: str) -> None:
        """Append to household notes."""
        p = self._household_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        line = content.strip()
        if not line.endswith("\n"):
            line += "\n"
        try:
            with p.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Could not append to household notes: %s", e)

    def list_users_from_notes(self) -> list[str]:
        """List user IDs from existing note files (excluding household)."""
        if not self._base.exists():
            return []
        users: list[str] = []
        for f in self._base.iterdir():
            if f.is_file() and f.suffix == ".md" and f.stem != "household":
                users.append(f.stem)
        return sorted(users)
