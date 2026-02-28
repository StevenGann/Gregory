"""Model selection: ask highest-priority model which AI to use for each message."""

import difflib
import logging
import re

from gregory.ai.config import ResolvedProvider, resolve_providers_ordered
from gregory.ai.prompts import MODEL_SELECTION_SYSTEM, build_model_selection_prompt
from gregory.ai.router import _instantiate
from gregory.config import get_settings

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Canonical form for comparison: lowercase, collapse runs of spaces/hyphens to one hyphen."""
    s = re.sub(r"[\s\-_]+", "-", s.strip().lower()).strip("-")
    return s


def _parse_model_id(response: str, valid_ids: set[str]) -> str | None:
    """Extract a valid model id from the selection model's response."""
    text = response.strip()
    text_lower = text.lower()

    # 1. Exact match
    for mid in valid_ids:
        if mid.lower() == text_lower:
            return mid

    # 2. Response contains the full model id
    for mid in valid_ids:
        if mid.lower() in text_lower:
            return mid

    # 3. Close match: normalize both and pick the best similarity above threshold
    norm_response = _normalize(text)
    if not norm_response:
        return None
    best_match: str | None = None
    best_ratio = 0.0
    for mid in valid_ids:
        norm_id = _normalize(mid)
        ratio = difflib.SequenceMatcher(None, norm_response, norm_id).ratio()
        if ratio > best_ratio and ratio >= 0.6:
            best_ratio = ratio
            best_match = mid
    return best_match


async def select_model_for_message(user_message: str) -> str | None:
    """
    Ask the highest-priority model which model should handle the message.
    Returns the chosen model id, or None to use default order.
    """
    resolved = resolve_providers_ordered()
    if not resolved:
        return None
    if len(resolved) == 1:
        logger.info("[model_select] Only one provider (%s), skipping selection", resolved[0].model)
        return resolved[0].model  # Only one option

    settings = get_settings()
    selection_provider = None
    if settings.model_selection_provider:
        pt = settings.model_selection_provider.strip().lower()
        if pt in ("ollama", "anthropic", "gemini"):
            for r in resolved:
                if r.provider_type == pt:
                    selection_provider = r
                    break
        if selection_provider is None:
            logger.warning(
                "[model_select] model_selection_provider=%s not found, using default order",
                settings.model_selection_provider,
            )
            return None
    else:
        selection_provider = resolved[0]
    provider_impl = _instantiate(selection_provider)
    if provider_impl is None:
        return None

    models = [(r.model, r.notes) for r in resolved]
    prompt = build_model_selection_prompt(user_message, models)

    available = [r.model for r in resolved]
    logger.info(
        "[model_select] Consulting %s (priority 1) to choose from %s | message: %.60s...",
        selection_provider.model,
        available,
        user_message[:60],
    )
    try:
        response = await provider_impl.generate(
            prompt=prompt,
            history=[],
            system_context=MODEL_SELECTION_SYSTEM,
        )
        logger.debug(
            "[model_select] Raw selection response: %r (valid ids: %s)",
            response.strip()[:200],
            available,
        )
        valid_ids = {r.model for r in resolved}
        chosen = _parse_model_id(response, valid_ids)
        if chosen:
            logger.info(
                "[model_select] Selected %s (raw response: %.80s)",
                chosen,
                response.strip()[:80],
            )
        else:
            logger.warning(
                "[model_select] Could not parse model from response, using default order (response: %.80s)",
                response.strip()[:80],
            )
        return chosen
    except Exception as e:
        logger.warning("[model_select] Selection failed, using default order: %s", e)
        return None


def reorder_providers_by_model(
    resolved: list[ResolvedProvider], chosen_model: str | None
) -> list[ResolvedProvider]:
    """Put the chosen model first; if not found or None, return original order."""
    if not chosen_model:
        return resolved
    for i, r in enumerate(resolved):
        if r.model == chosen_model:
            reordered = [r] + resolved[:i] + resolved[i + 1 :]
            order = [p.model for p in reordered]
            logger.info("[model_select] Reordered providers: %s", order)
            return reordered
    logger.warning("[model_select] Chosen model %s not in list, keeping default order", chosen_model)
    return resolved
