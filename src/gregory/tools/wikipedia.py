"""Wikipedia search via the public MediaWiki API."""

import logging

import httpx

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# Wikipedia requires a descriptive User-Agent per https://meta.wikimedia.org/wiki/User-Agent_policy
USER_AGENT = "GregoryHouseAI/1.0 (https://github.com; house AI assistant)"


async def search_wikipedia(query: str, max_results: int = 3) -> list[dict]:
    """Search Wikipedia and return summaries for top matching articles.

    Each result dict has: title, url, summary, snippet.
    Returns empty list on error or no matches.
    """
    query = query.strip()
    if not query:
        return []

    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # 1. Search for matching articles
            search_resp = await client.get(
                WIKIPEDIA_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_results,
                    "format": "json",
                    "origin": "*",
                },
            )
            search_resp.raise_for_status()
            data = search_resp.json()
            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                logger.info("[wikipedia] No results for %r", query)
                return []

            # 2. Fetch extracts for the top results
            page_ids = [str(r["pageid"]) for r in search_results]
            titles = {str(r["pageid"]): r["title"] for r in search_results}
            snippets = {str(r["pageid"]): r.get("snippet", "") for r in search_results}

            extract_resp = await client.get(
                WIKIPEDIA_API,
                params={
                    "action": "query",
                    "pageids": "|".join(page_ids),
                    "prop": "extracts|info",
                    "exintro": True,
                    "explaintext": True,
                    "exsentences": 3,
                    "inprop": "url",
                    "format": "json",
                    "origin": "*",
                },
            )
            extract_resp.raise_for_status()
            pages = extract_resp.json().get("query", {}).get("pages", {})

            results: list[dict] = []
            for page_id, page in pages.items():
                if page.get("missing") or "extract" not in page:
                    summary = snippets.get(page_id, "")
                else:
                    summary = page.get("extract", "").strip() or snippets.get(page_id, "")
                title = page.get("title") or titles.get(page_id, "Unknown")
                url = page.get("fullurl", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
                results.append({
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "snippet": snippets.get(page_id, ""),
                })
            return results

    except httpx.HTTPError as e:
        logger.warning("[wikipedia] HTTP error for %r: %s", query, e)
        return []
    except Exception as e:
        logger.exception("[wikipedia] Search failed for %r: %s", query, e)
        return []


def format_wikipedia_context(results: list[dict]) -> str:
    """Format Wikipedia results as context text for the AI."""
    if not results:
        return ""
    lines: list[str] = []
    for r in results:
        lines.append(f"### {r['title']}")
        lines.append(r.get("summary", r.get("snippet", "")))
        if r.get("url"):
            lines.append(f"Source: {r['url']}")
        lines.append("")
    return "## Wikipedia search results\n\n" + "\n".join(lines).strip()
