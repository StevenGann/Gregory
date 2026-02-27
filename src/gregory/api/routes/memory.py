"""Memory route - GET /memory/search."""

import logging

from fastapi import APIRouter, Query

from gregory.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    top_k: int = Query(default=5, ge=1, le=20, description="Maximum results to return"),
) -> dict:
    """Search Gregory's journal memory (vector DB).

    Returns matching journal entries sorted by relevance. Uses threshold=0.0 so
    all entries are returned ordered by similarity — suitable for inspection and
    debugging. The chat pipeline uses the configurable MEMORY_SIMILARITY_THRESHOLD.
    """
    settings = get_settings()
    if not settings.memory_enabled:
        return {"results": [], "message": "Memory system is disabled (set MEMORY_ENABLED=true)"}

    from gregory.memory.service import get_vector_store

    vector_store = get_vector_store()
    hits = await vector_store.search(query=q, n_results=top_k, threshold=0.0)

    return {
        "results": [
            {
                "text": h["text"],
                "date": h["metadata"].get("date", ""),
                "user_id": h["metadata"].get("user_id", ""),
                "type": h["metadata"].get("type", ""),
                "similarity": round(h["similarity"], 4),
            }
            for h in hits
        ]
    }
