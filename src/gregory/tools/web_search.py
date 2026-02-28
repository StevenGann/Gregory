"""Web search via ddgs (DuckDuckGo, Bing, etc.)."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return snippets for matching results.

    Each result dict has: title, url, snippet.
    Returns empty list on error or no matches.
    """
    query = query.strip()
    if not query:
        return []

    def _search() -> list[dict]:
        try:
            from ddgs import DDGS

            raw = DDGS().text(query, max_results=max_results)
            results: list[dict] = []
            for r in raw:
                results.append({
                    "title": r.get("title", "Unknown"),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                })
            return results
        except Exception as e:
            logger.warning("[web_search] Search failed for %r: %s", query, e)
            return []

    try:
        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.exception("[web_search] Async search failed for %r: %s", query, e)
        return []


def format_web_search_context(results: list[dict]) -> str:
    """Format web search results as context text for the AI."""
    if not results:
        return ""
    lines: list[str] = []
    for r in results:
        lines.append(f"### {r.get('title', 'Unknown')}")
        lines.append(r.get("snippet", ""))
        if r.get("url"):
            lines.append(f"Source: {r['url']}")
        lines.append("")
    return "## Web search results\n\n" + "\n".join(lines).strip()
