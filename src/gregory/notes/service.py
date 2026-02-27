"""Notes service - read/write Markdown notes per user, household, Gregory, and entities."""

import logging
from pathlib import Path

from gregory.config import get_settings

logger = logging.getLogger(__name__)

HOUSEHOLD_FILE = "household.md"
GREGORY_FILE = "gregory.md"
ENTITIES_DIR = "entities"

# Note types that are not per-user (excluded from list_users_from_notes)
_RESERVED_STEMS = frozenset({"household", "gregory"})


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

    def _gregory_path(self) -> Path:
        """Path to Gregory's self-notes."""
        return self._base / GREGORY_FILE

    def _entities_dir(self) -> Path:
        """Path to entities notes directory."""
        return self._base / ENTITIES_DIR

    def _entity_path(self, entity_id: str) -> Path:
        """Path to entity notes file (sanitized)."""
        safe = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in entity_id.lower()
        )
        return self._entities_dir() / f"{safe}.md"

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

    def read_gregory(self) -> str:
        """Read Gregory's self-notes (experiences, thoughts, preferences)."""
        p = self._gregory_path()
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read Gregory notes: %s", e)
            return ""

    def read_entities(self) -> dict[str, str]:
        """Read all entity notes (e.g. dog, house, project). Returns {entity_id: content}."""
        entities_dir = self._entities_dir()
        if not entities_dir.exists():
            return {}
        result: dict[str, str] = {}
        for f in sorted(entities_dir.iterdir()):
            if f.is_file() and f.suffix == ".md":
                try:
                    result[f.stem] = f.read_text(encoding="utf-8").strip()
                except OSError as e:
                    logger.warning("Could not read entity notes %s: %s", f.stem, e)
        return result

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

    def append_gregory(self, content: str) -> None:
        """Append to Gregory's self-notes."""
        p = self._gregory_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        line = content.strip()
        if not line.endswith("\n"):
            line += "\n"
        try:
            with p.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Could not append to Gregory notes: %s", e)

    def write_household(self, content: str) -> None:
        """Overwrite household notes entirely."""
        p = self._household_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content.strip() + "\n" if content.strip() else "", encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write household notes: %s", e)

    def write_gregory(self, content: str) -> None:
        """Overwrite Gregory's self-notes entirely."""
        p = self._gregory_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content.strip() + "\n" if content.strip() else "", encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write Gregory notes: %s", e)

    def write_entity(self, entity_id: str, content: str) -> None:
        """Overwrite entity notes entirely."""
        p = self._entity_path(entity_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content.strip() + "\n" if content.strip() else "", encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write entity notes %s: %s", entity_id, e)

    def write_user(self, user_id: str, content: str) -> None:
        """Overwrite user notes entirely."""
        p = self._path(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content.strip() + "\n" if content.strip() else "", encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write notes for %s: %s", user_id, e)

    def list_note_documents(self) -> list[tuple[str, str]]:
        """List note documents that have content, as (doc_type, doc_id). Types: household, gregory, entity, user."""
        docs: list[tuple[str, str]] = []
        if self.read_household().strip():
            docs.append(("household", "household"))
        if self.read_gregory().strip():
            docs.append(("gregory", "gregory"))
        for entity_id, content in self.read_entities().items():
            if content.strip():
                docs.append(("entity", entity_id))
        for stem in self.list_users_from_notes():
            if self.read_user(stem).strip():
                docs.append(("user", stem))
        return docs

    def read_document(self, doc_type: str, doc_id: str) -> str:
        """Read a note document by type and id."""
        if doc_type == "household":
            return self.read_household()
        if doc_type == "gregory":
            return self.read_gregory()
        if doc_type == "entity":
            return self.read_entities().get(doc_id, "")
        if doc_type == "user":
            return self.read_user(doc_id)
        return ""

    def write_document(self, doc_type: str, doc_id: str, content: str) -> None:
        """Overwrite a note document by type and id."""
        if doc_type == "household":
            self.write_household(content)
        elif doc_type == "gregory":
            self.write_gregory(content)
        elif doc_type == "entity":
            self.write_entity(doc_id, content)
        elif doc_type == "user":
            self.write_user(doc_id, content)

    def append_entity(self, entity_id: str, content: str) -> None:
        """Append to notes for an entity (e.g. dog, house)."""
        p = self._entity_path(entity_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        line = content.strip()
        if not line.endswith("\n"):
            line += "\n"
        try:
            with p.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError as e:
            logger.warning("Could not append to entity notes %s: %s", entity_id, e)

    def list_users_from_notes(self) -> list[str]:
        """List user IDs from root-level note files (excluding household, gregory)."""
        if not self._base.exists():
            return []
        users: list[str] = []
        for f in self._base.iterdir():
            if f.is_file() and f.suffix == ".md" and f.stem not in _RESERVED_STEMS:
                users.append(f.stem)
        return sorted(users)
