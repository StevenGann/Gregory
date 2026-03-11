"""Obsidian-style [[wikilink]] support for Gregory notes.

Parses ``[[title]]`` links in note text and resolves them to note content,
enabling enriched context assembly where linked notes contribute brief summaries.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Matches [[anything]] — we capture the inner text
_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

# Separator between the display text and target in [[target|display]] syntax
# We only care about the target portion.
_ALIAS_SEP = "|"


def parse_wikilinks(text: str) -> list[str]:
    """Extract all [[title]] link targets from text.

    Handles [[target]] and [[target|display text]] (Obsidian alias syntax).
    Returns list of target strings (de-duplicated, in order of first appearance).
    """
    seen: set[str] = set()
    targets: list[str] = []
    for m in _WIKILINK_RE.finditer(text):
        inner = m.group(1).strip()
        # Handle [[target|display]] — take the part before the pipe
        target = inner.split(_ALIAS_SEP, 1)[0].strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def _slugify(title: str) -> str:
    """Normalize a title to a filesystem slug for lookup."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    return slug.strip("_")


def resolve_wikilink(title: str, notes_service) -> str | None:
    """Return note content for a wikilink target title, or None if not found.

    Resolution order (first match wins):
    1. knowledge/{slug}.md
    2. entities/{slug}.md
    3. {slug}.md  (user notes and special files: household, gregory, services)

    The *notes_service* is a ``NotesService`` instance.
    """
    slug = _slugify(title)
    if not slug:
        return None

    # 1. Knowledge notes
    kdir = notes_service._knowledge_dir()
    if kdir.exists():
        kpath = kdir / f"{slug}.md"
        if kpath.exists():
            try:
                return kpath.read_text(encoding="utf-8")
            except OSError:
                pass

    # 2. Entity notes
    edir = notes_service._entities_dir()
    if edir.exists():
        epath = edir / f"{slug}.md"
        if epath.exists():
            try:
                return epath.read_text(encoding="utf-8")
            except OSError:
                pass

    # 3. Root notes (user notes, household, gregory, services)
    rpath = notes_service._base / f"{slug}.md"
    if rpath.exists():
        try:
            return rpath.read_text(encoding="utf-8")
        except OSError:
            pass

    return None


def _extract_summary(content: str, max_chars: int = 300) -> str:
    """Return a brief summary of a note.

    Prefers the ``summary:`` field from YAML frontmatter, then falls back to
    the first non-empty, non-header paragraph after any frontmatter block.
    """
    if not content.strip():
        return ""

    # Check for frontmatter summary field
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end]
            for line in frontmatter.splitlines():
                if line.lower().startswith("summary:"):
                    summary = line.split(":", 1)[1].strip()
                    if summary:
                        return summary
            # Skip past frontmatter for body
            body = content[end + 3:].strip()
        else:
            body = content
    else:
        body = content

    # Find first non-empty, non-header line
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return line[:max_chars]

    return body[:max_chars].strip()


def get_link_summaries(
    text: str,
    notes_service,
    max_depth: int = 1,
    _visited: set[str] | None = None,
) -> dict[str, str]:
    """Follow [[links]] in text and return {title: summary} for each resolved note.

    Cycle-safe: tracks visited slugs.  Respects ``max_depth`` to prevent
    unbounded traversal.

    Args:
        text: Note content to scan for wikilinks.
        notes_service: NotesService instance.
        max_depth: How many levels of links to follow (1 = direct links only).
        _visited: Internal set of already-visited slugs (for cycle detection).

    Returns:
        Dict mapping display title → brief summary string.
    """
    if max_depth <= 0:
        return {}

    if _visited is None:
        _visited = set()

    summaries: dict[str, str] = {}
    targets = parse_wikilinks(text)

    for title in targets:
        slug = _slugify(title)
        if not slug or slug in _visited:
            continue
        _visited.add(slug)

        content = resolve_wikilink(title, notes_service)
        if content is None:
            logger.debug("[links] Unresolved wikilink: %r", title)
            continue

        summary = _extract_summary(content)
        summaries[title] = summary

        # Recurse into linked note's own links (depth - 1)
        if max_depth > 1:
            child_summaries = get_link_summaries(
                content,
                notes_service,
                max_depth=max_depth - 1,
                _visited=_visited,
            )
            for child_title, child_summary in child_summaries.items():
                if child_title not in summaries:
                    summaries[child_title] = child_summary

    return summaries
