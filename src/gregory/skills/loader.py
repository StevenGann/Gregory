"""Build and return the application-wide skill registry.

Called once during FastAPI lifespan startup (main.py).  Each built-in skill is
instantiated with its enabled/disabled state derived from Settings.  MCP skills
are registered separately by the MCP client manager after server connections are
established.
"""

from __future__ import annotations

import logging

from gregory.config import get_settings
from gregory.skills.base import SkillRegistry, set_registry
from gregory.skills.home_assistant import HomeAssistantSkill
from gregory.skills.web_search import WebSearchSkill
from gregory.skills.wikipedia import WikipediaSkill

logger = logging.getLogger(__name__)


def build_registry() -> SkillRegistry:
    """Instantiate all built-in skills, register them, and return the registry.

    The registry is also stored as the application singleton via set_registry().
    """
    settings = get_settings()
    registry = SkillRegistry()

    # Skills listed in skills_enabled filter (empty list = all enabled)
    allowed: set[str] = set(settings.skills_enabled) if settings.skills_enabled else set()

    def _enabled(name: str, default: bool) -> bool:
        if allowed and name not in allowed:
            return False
        return default

    registry.register(WikipediaSkill(enabled=_enabled("wikipedia", settings.wikipedia_enabled)))
    registry.register(WebSearchSkill(enabled=_enabled("web_search", settings.web_search_enabled)))
    registry.register(
        HomeAssistantSkill(
            enabled=_enabled(
                "home_assistant",
                bool(settings.ha_enabled and settings.ha_base_url and settings.ha_access_token),
            )
        )
    )

    set_registry(registry)
    logger.info(
        "[skills] Registry built with %d skills (%d enabled)",
        len(registry._skills),
        len(registry.get_enabled_skills()),
    )
    return registry
