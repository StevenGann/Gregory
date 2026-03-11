"""Base types for the Gregory skill system."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Result of a skill execution."""

    skill_name: str
    query: str
    content: str  # formatted markdown block ready to inject as context
    success: bool
    error: str = ""


@runtime_checkable
class Skill(Protocol):
    """Protocol that all Gregory skills must implement."""

    name: str
    """Unique identifier e.g. 'wikipedia', 'web_search', 'home_assistant'."""

    marker_pattern: re.Pattern
    """Compiled regex that matches the marker(s) this skill handles in AI responses."""

    instruction: str
    """Text injected into the system prompt describing how to use this skill."""

    enabled: bool
    """When False the skill is registered but never executed and its instructions
    are omitted from the system prompt."""

    async def execute(self, query: str) -> SkillResult:
        """Execute the skill for the extracted *query* string.

        The *query* is the content captured by marker_pattern group 1.
        Returns a SkillResult with ``content`` ready to inject into the
        follow-up AI context.
        """
        ...


class SkillRegistry:
    """Registry of Gregory skills.

    Skills are registered in order and queried by scanning AI response text for
    marker patterns.  The registry builds the combined instruction block for the
    system prompt and executes all matched skill requests.
    """

    def __init__(self) -> None:
        self._skills: list[Skill] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, skill: Skill) -> None:
        """Add a skill to the registry."""
        self._skills.append(skill)
        logger.debug("[skills] Registered skill: %s (enabled=%s)", skill.name, skill.enabled)

    def get_enabled_skills(self) -> list[Skill]:
        """Return all enabled skills in registration order."""
        return [s for s in self._skills if s.enabled]

    # ------------------------------------------------------------------
    # System-prompt support
    # ------------------------------------------------------------------

    def build_instructions(self) -> str:
        """Return combined instruction text for all enabled skills."""
        parts = [s.instruction for s in self.get_enabled_skills() if s.instruction.strip()]
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Marker extraction & execution
    # ------------------------------------------------------------------

    def extract_requests(self, text: str) -> list[tuple[Skill, str]]:
        """Scan *text* for skill markers and return (skill, query) pairs.

        A single piece of text may contain multiple markers, possibly for
        different skills.  All are returned in document order.
        """
        requests: list[tuple[Skill, str]] = []
        for skill in self.get_enabled_skills():
            for m in skill.marker_pattern.finditer(text):
                query = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else ""
                requests.append((skill, query))
        return requests

    async def execute_all(self, text: str) -> list[SkillResult]:
        """Execute all skills whose markers appear in *text*.

        Returns results in document order.  Failures are caught and returned as
        unsuccessful SkillResults rather than raised.
        """
        results: list[SkillResult] = []
        for skill, query in self.extract_requests(text):
            try:
                result = await skill.execute(query)
                results.append(result)
            except Exception as e:
                logger.warning("[skills] Skill %r failed for query %r: %s", skill.name, query, e)
                results.append(
                    SkillResult(
                        skill_name=skill.name,
                        query=query,
                        content=f"## {skill.name} error\n\nSkill failed: {e}",
                        success=False,
                        error=str(e),
                    )
                )
        return results


# Module-level singleton, populated by loader.py during startup.
_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    """Return the application-wide skill registry, creating it if needed."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def set_registry(registry: SkillRegistry) -> None:
    """Replace the application-wide skill registry (used in tests)."""
    global _registry
    _registry = registry
