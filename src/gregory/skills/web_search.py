"""Web search skill — handles [WEB_SEARCH: query] markers."""

from __future__ import annotations

import re

from gregory.skills.base import SkillResult

MARKER = re.compile(r"\[WEB_SEARCH:\s*([^\]]+)\]", re.IGNORECASE)

INSTRUCTION = """
## Web search

For current events, recent news, or information that may not be in Wikipedia (product info, local events, real-time data), use web search:
- [WEB_SEARCH: query] — search the web; you will receive results and can answer immediately

**When to use web search instead of or in addition to Wikipedia:**
- Breaking news, recent developments, "latest on X"
- Product reviews, prices, availability
- Local events, weather, traffic
- Anything that changes frequently or is too new for Wikipedia

**How:** Add [WEB_SEARCH: query] at the end of your response. Use a clear search term. You will get snippets from top results."""


class WebSearchSkill:
    """Skill that runs DuckDuckGo web searches for [WEB_SEARCH: query] markers."""

    name = "web_search"
    marker_pattern = MARKER
    instruction = INSTRUCTION
    enabled: bool = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def execute(self, query: str) -> SkillResult:
        from gregory.tools.web_search import format_web_search_context, search_web

        results = await search_web(query, max_results=5)
        content = format_web_search_context(results)
        if not content:
            content = "## Web search results\n\nNo results found."
        return SkillResult(
            skill_name=self.name,
            query=query,
            content=content,
            success=bool(results),
        )
