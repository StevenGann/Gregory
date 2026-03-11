"""Load notes as context for AI chat."""

from gregory.config import get_settings
from gregory.notes.service import NotesService


def load_all_notes() -> str:
    """Load household + Gregory + services + entities (no per-user notes). For background tasks."""
    notes = NotesService()
    household = notes.read_household()
    gregory_notes = notes.read_gregory()
    services = notes.read_services()
    entities = notes.read_entities()

    parts: list[str] = []
    if household:
        parts.append("## Household notes\n" + household.strip())
    if gregory_notes:
        parts.append("## Gregory's notes (about himself)\n" + gregory_notes.strip())
    if services:
        parts.append("## Local services and contacts\n" + services.strip())
    for entity_id, content in entities.items():
        if content:
            parts.append(f"## Notes about {entity_id}\n" + content)
    if not parts:
        return ""
    return "\n\n".join(parts)


def load_notes_for_chat(user_id: str) -> str:
    """Load household + Gregory + services + entities + user notes as context for chat.

    When ``wikilinks_enabled`` is True (from settings), scans all loaded note content
    for ``[[wikilinks]]`` and appends brief summaries of any resolved linked notes.
    """
    settings = get_settings()
    notes = NotesService()
    household = notes.read_household()
    gregory_notes = notes.read_gregory()
    services = notes.read_services()
    entities = notes.read_entities()
    user = notes.read_user(user_id)

    parts: list[str] = []
    if household:
        parts.append("## Household notes\n" + household.strip())
    if gregory_notes:
        parts.append("## Gregory's notes (about himself)\n" + gregory_notes.strip())
    if services:
        parts.append("## Local services and contacts\n" + services.strip())
    for entity_id, content in entities.items():
        if content:
            parts.append(f"## Notes about {entity_id}\n" + content)
    if user:
        parts.append(f"## Notes about {user_id}\n" + user.strip())
    if not parts:
        return ""

    primary_context = "\n\n".join(parts)

    # Wikilink enrichment: append summaries of linked notes
    wikilinks_enabled = getattr(settings, "wikilinks_enabled", False)
    wikilink_depth = getattr(settings, "wikilink_depth", 1)
    if wikilinks_enabled and wikilink_depth > 0:
        from gregory.notes.links import get_link_summaries
        summaries = get_link_summaries(primary_context, notes, max_depth=wikilink_depth)
        if summaries:
            ref_lines: list[str] = ["## Referenced notes"]
            for title, summary in summaries.items():
                if summary:
                    ref_lines.append(f"\n### {title}\n{summary}")
            primary_context = primary_context + "\n\n" + "\n".join(ref_lines)

    return primary_context
