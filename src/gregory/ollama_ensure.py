"""Ensure configured Ollama models are available; pull missing ones on startup."""

import asyncio
import logging
from typing import Any

import httpx

from gregory.ai.config import get_ai_providers_config
from gregory.config import get_settings

logger = logging.getLogger(__name__)

OLLAMA_TAGS_URL = "/api/tags"
OLLAMA_PULL_URL = "/api/pull"
OLLAMA_TIMEOUT = 30.0


def _model_matches(available_name: str, configured_id: str) -> bool:
    """Check if configured model id matches an available model name."""
    return available_name == configured_id or available_name.startswith(configured_id + ":")


async def _get_available_models(base_url: str) -> set[str]:
    """Fetch list of available model names from Ollama."""
    url = f"{base_url.rstrip('/')}{OLLAMA_TAGS_URL}"
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            models = data.get("models", [])
            return {m.get("name", "") for m in models if m.get("name")}
    except Exception as e:
        logger.warning("Could not fetch Ollama models from %s: %s", url, e)
        return set()


async def _pull_model(base_url: str, model_id: str) -> bool:
    """Trigger ollama pull for a model. Returns True if successful."""
    url = f"{base_url.rstrip('/')}{OLLAMA_PULL_URL}"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(url, json={"model": model_id, "stream": False})
            r.raise_for_status()
            logger.info("Pulled Ollama model %s from %s", model_id, base_url)
            return True
    except Exception as e:
        logger.error("Failed to pull Ollama model %s from %s: %s", model_id, base_url, e)
        return False


async def ensure_ollama_models() -> None:
    """
    For each Ollama endpoint in ai_providers, check configured models are available.
    Pull any that are missing. Runs in background to avoid blocking startup.
    """
    settings = get_settings()
    if not getattr(settings, "ollama_ensure_models", False):
        return

    ai_config = get_ai_providers_config()
    if not ai_config or not ai_config.ollama:
        return

    async def _ensure_endpoint(ep: Any) -> None:
        base_url = getattr(ep, "url", None) or (ep.get("url") if isinstance(ep, dict) else None)
        if not base_url:
            return
        models = getattr(ep, "models", None) or (ep.get("models", []) if isinstance(ep, dict) else [])
        configured = [m.id if hasattr(m, "id") else m.get("id") for m in models]
        if not configured:
            return
        available = await _get_available_models(base_url)
        missing = [mid for mid in configured if not any(_model_matches(a, mid) for a in available)]
        if missing:
            logger.info(
                "Ollama %s: missing models %s, pulling in background...",
                base_url,
                missing,
            )
            for mid in missing:
                await _pull_model(base_url, mid)

    for ep in ai_config.ollama:
        try:
            await _ensure_endpoint(ep)
        except Exception as e:
            logger.warning("Error ensuring Ollama models for %s: %s", ep, e)


def run_ollama_ensure_on_startup() -> None:
    """Spawn background task to ensure Ollama models. Call from FastAPI lifespan."""
    asyncio.create_task(ensure_ollama_models())
