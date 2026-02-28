"""AI provider and model configuration."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from gregory.config import get_settings

logger = logging.getLogger(__name__)


class ModelInfo(BaseModel):
    """Model identifier with optional suitability notes."""

    id: str = Field(..., description="Model identifier (e.g. llama3.2, claude-sonnet-4-6)")
    notes: str = Field(default="", description="What this model is best suited for")


class OllamaEndpoint(BaseModel):
    """Ollama server with its available models."""

    url: str = Field(..., description="Ollama server URL (e.g. http://localhost:11434)")
    models: list[ModelInfo] = Field(default_factory=list)


class AnthropicInstance(BaseModel):
    """Anthropic API key with its available models."""

    api_key: str | None = Field(default=None, description="API key (prefer api_key_env for secrets)")
    api_key_env: str | None = Field(default=None, description="Env var name to read API key from")
    models: list[ModelInfo] = Field(default_factory=list)


class GeminiInstance(BaseModel):
    """Gemini API key with its available models."""

    api_key: str | None = Field(default=None, description="API key (prefer api_key_env for secrets)")
    api_key_env: str | None = Field(default=None, description="Env var name to read API key from")
    models: list[ModelInfo] = Field(default_factory=list)


class AIProvidersConfig(BaseModel):
    """Multi-provider, multi-model configuration."""

    ollama: list[OllamaEndpoint] = Field(default_factory=list)
    anthropic: list[AnthropicInstance] = Field(default_factory=list)
    gemini: list[GeminiInstance] = Field(default_factory=list)


class ModelPriorityEntry(BaseModel):
    """Single entry in model selection priority order."""

    provider: str = Field(..., description="ollama, anthropic, or gemini")
    instance: int = Field(default=0, description="Index into the provider's instance list")
    model: str = Field(..., description="Model ID to use")


@dataclass
class ResolvedProvider:
    """A provider ready to instantiate, with credentials and model."""

    provider_type: str
    display_name: str
    api_key: str | None
    base_url: str | None
    model: str
    notes: str


def get_ollama_url_for_embeddings() -> str | None:
    """Resolve Ollama URL for memory embeddings. Checks ollama_base_url first, then ai_providers."""
    settings = get_settings()
    if settings.ollama_base_url:
        return settings.ollama_base_url.rstrip("/")
    ai_config = get_ai_providers_config()
    if ai_config and ai_config.ollama:
        first = ai_config.ollama[0]
        url = getattr(first, "url", None) or (
            first.get("url") if isinstance(first, dict) else None
        )
        if url:
            return url.rstrip("/")
    return None


def _resolve_api_key(instance: AnthropicInstance | GeminiInstance) -> str | None:
    """Resolve API key from api_key or api_key_env."""
    if instance.api_key:
        return instance.api_key
    if instance.api_key_env:
        return os.environ.get(instance.api_key_env) or None
    return None


def get_ai_providers_config() -> AIProvidersConfig | None:
    """Load ai_providers from config.json. Returns None if not present or empty."""
    settings = get_settings()
    raw = settings.ai_providers
    if raw is None:
        return None
    if isinstance(raw, dict) and not any(raw.get(k) for k in ("ollama", "anthropic", "gemini")):
        return None
    try:
        return AIProvidersConfig.model_validate(raw)
    except Exception as e:
        logger.warning(
            "[config] ai_providers validation failed, falling back to legacy config: %s",
            e,
        )
        return None


def get_model_priority() -> list[ModelPriorityEntry]:
    """Load model_priority from config. Returns empty if not present."""
    settings = get_settings()
    raw = settings.model_priority
    if raw is None or not raw:
        return []
    result = []
    for item in raw:
        if isinstance(item, ModelPriorityEntry):
            result.append(item)
        elif isinstance(item, dict):
            result.append(ModelPriorityEntry.model_validate(item))
        else:
            result.append(ModelPriorityEntry.model_validate(item))
    return result


def resolve_providers_ordered() -> list[ResolvedProvider]:
    """
    Build ordered list of providers from config.
    Uses ai_providers + model_priority if set; otherwise falls back to legacy flat config.
    """
    ai_config = get_ai_providers_config()
    priority = get_model_priority()

    if ai_config and (ai_config.ollama or ai_config.anthropic or ai_config.gemini):
        # New config: build from ai_providers and model_priority
        return _resolve_from_ai_config(ai_config, priority)
    # Legacy: build from flat OLLAMA_BASE_URL, ANTHROPIC_API_KEY, etc.
    return _resolve_from_legacy_config(priority)


def _resolve_from_ai_config(
    ai_config: AIProvidersConfig,
    priority: list[ModelPriorityEntry],
) -> list[ResolvedProvider]:
    """Build provider list from ai_providers config."""
    result: list[ResolvedProvider] = []

    def add_ollama():
        for i, ep in enumerate(ai_config.ollama):
            for m in ep.models:
                result.append(
                    ResolvedProvider(
                        provider_type="ollama",
                        display_name=f"ollama:{ep.url}:{m.id}",
                        api_key=None,
                        base_url=ep.url.rstrip("/"),
                        model=m.id,
                        notes=m.notes,
                    )
                )

    def add_anthropic():
        for i, inst in enumerate(ai_config.anthropic):
            key = _resolve_api_key(inst)
            if not key:
                continue
            for m in inst.models:
                result.append(
                    ResolvedProvider(
                        provider_type="anthropic",
                        display_name=f"anthropic:{m.id}",
                        api_key=key,
                        base_url=None,
                        model=m.id,
                        notes=m.notes,
                    )
                )

    def add_gemini():
        for i, inst in enumerate(ai_config.gemini):
            key = _resolve_api_key(inst)
            if not key:
                continue
            for m in inst.models:
                result.append(
                    ResolvedProvider(
                        provider_type="gemini",
                        display_name=f"gemini:{m.id}",
                        api_key=key,
                        base_url=None,
                        model=m.id,
                        notes=m.notes,
                    )
                )

    if priority:
        # Use explicit priority: lookup by (provider, instance index, model)
        all_ollama = list(ai_config.ollama)
        all_anthropic = list(ai_config.anthropic)
        all_gemini = list(ai_config.gemini)

        for entry in priority:
            if entry.provider == "ollama" and entry.instance < len(all_ollama):
                ep = all_ollama[entry.instance]
                for m in ep.models:
                    if m.id == entry.model:
                        result.append(
                            ResolvedProvider(
                                provider_type="ollama",
                                display_name=f"ollama:{ep.url}:{m.id}",
                                api_key=None,
                                base_url=ep.url.rstrip("/"),
                                model=m.id,
                                notes=m.notes,
                            )
                        )
                        break
            elif entry.provider == "anthropic" and entry.instance < len(all_anthropic):
                inst = all_anthropic[entry.instance]
                key = _resolve_api_key(inst)
                if not key:
                    continue
                for m in inst.models:
                    if m.id == entry.model:
                        result.append(
                            ResolvedProvider(
                                provider_type="anthropic",
                                display_name=f"anthropic:{m.id}",
                                api_key=key,
                                base_url=None,
                                model=m.id,
                                notes=m.notes,
                            )
                        )
                        break
            elif entry.provider == "gemini" and entry.instance < len(all_gemini):
                inst = all_gemini[entry.instance]
                key = _resolve_api_key(inst)
                if not key:
                    continue
                for m in inst.models:
                    if m.id == entry.model:
                        result.append(
                            ResolvedProvider(
                                provider_type="gemini",
                                display_name=f"gemini:{m.id}",
                                api_key=key,
                                base_url=None,
                                model=m.id,
                                notes=m.notes,
                            )
                        )
                        break
    else:
        # Default order: ollama first (cheap/free), then gemini, then anthropic (expensive)
        add_ollama()
        add_gemini()
        add_anthropic()

    return result


def _resolve_from_legacy_config(priority: list[ModelPriorityEntry]) -> list[ResolvedProvider]:
    """Build provider list from legacy flat config (OLLAMA_BASE_URL, etc.)."""
    settings = get_settings()
    result: list[ResolvedProvider] = []
    order = ["ollama", "gemini", "anthropic"]
    preferred = (settings.ai_provider or "").strip().lower()
    if preferred and preferred in order:
        order = [preferred] + [p for p in order if p != preferred]

    for name in order:
        if name == "ollama" and settings.ollama_base_url:
            result.append(
                ResolvedProvider(
                    provider_type="ollama",
                    display_name="ollama",
                    api_key=None,
                    base_url=settings.ollama_base_url.rstrip("/"),
                    model=settings.ollama_model,
                    notes="",
                )
            )
        elif name == "anthropic" and settings.anthropic_api_key:
            result.append(
                ResolvedProvider(
                    provider_type="anthropic",
                    display_name="anthropic",
                    api_key=settings.anthropic_api_key,
                    base_url=None,
                    model=settings.claude_model,
                    notes="",
                )
            )
        elif name == "gemini" and settings.gemini_api_key:
            result.append(
                ResolvedProvider(
                    provider_type="gemini",
                    display_name="gemini",
                    api_key=settings.gemini_api_key,
                    base_url=None,
                    model=settings.gemini_model,
                    notes="",
                )
            )
    return result
