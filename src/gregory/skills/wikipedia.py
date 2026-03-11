"""Wikipedia skill — handles [WIKIPEDIA: query] markers."""

from __future__ import annotations

import re

from gregory.skills.base import SkillResult

MARKER = re.compile(r"\[WIKIPEDIA:\s*([^\]]+)\]", re.IGNORECASE)

INSTRUCTION = """
## Wikipedia verification (non-negotiable)

Whenever you are about to make a factual claim about any of the following—do NOT answer first. Search Wikipedia first, then answer. No deliberation, no explaining why you're searching. Just emit the marker and you will receive the results immediately.

**Always search first for:**
- Dates, years, or when something happened
- Locations, places, buildings, landmarks, MRT stations, addresses
- Current events, recent news, or anything that may have changed
- Any verifiable fact you are less than 95% certain about
- Names of people, organizations, products, or technical terms you might misremember

**Rule:** If in doubt, search. Accuracy over conversational smoothness. Do not rationalize your way out of verifying—your confidence is unreliable.

**How:** Add [WIKIPEDIA: query] at the end of your response. Use the exact search term that will find the answer (e.g. [WIKIPEDIA: Hume MRT station] not [WIKIPEDIA: Singapore train]). You will get the results and can then provide an accurate answer."""


class WikipediaSkill:
    """Skill that fetches Wikipedia summaries for [WIKIPEDIA: query] markers."""

    name = "wikipedia"
    marker_pattern = MARKER
    instruction = INSTRUCTION
    enabled: bool = True

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    async def execute(self, query: str) -> SkillResult:
        from gregory.tools.wikipedia import format_wikipedia_context, search_wikipedia

        results = await search_wikipedia(query, max_results=3)
        content = format_wikipedia_context(results)
        if not content:
            content = "## Wikipedia search results\n\nNo results found."
        return SkillResult(
            skill_name=self.name,
            query=query,
            content=content,
            success=bool(results),
        )
