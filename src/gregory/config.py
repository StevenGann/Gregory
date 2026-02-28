"""Configuration via environment variables and optional JSON file."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Tuple, Type

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """Application settings loaded from JSON file (when not in Docker), .env, and environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    # Ollama
    ollama_base_url: str | None = Field(
        default=None,
        description="Ollama server URL (e.g. http://192.168.1.x:11434)",
    )
    ollama_model: str = Field(
        default="llama3.2",
        description="Ollama model name (e.g. llama3.2, mistral)",
    )

    # Claude (Anthropic)
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude",
    )
    claude_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model identifier",
    )

    # Gemini (Google)
    gemini_api_key: str | None = Field(
        default=None,
        description="Google API key for Gemini",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model identifier",
    )

    # Provider selection (claude | gemini | ollama; if unset, first available wins)
    ai_provider: str | None = Field(
        default=None,
        description="Preferred AI provider: claude, gemini, or ollama",
    )

    # Notes observations (Gregory writes learned facts back to notes)
    observations_enabled: bool = Field(
        default=False,
        description="Enable AI to append observations to notes",
    )

    # Model routing: consult highest-priority model to pick best provider for each message
    model_routing_enabled: bool = Field(
        default=True,
        description="Ask highest-priority model which AI to use for each message",
    )
    model_selection_provider: str | None = Field(
        default=None,
        description="Force model selection to use this provider: 'ollama', 'anthropic', 'gemini', or null to use first in model_priority.",
    )
    model_routing_skip_simple: bool = Field(
        default=True,
        description="When true, skip model selection for short/simple messages (greetings, thanks, ok) and use config order.",
    )
    follow_up_prefer_ollama: bool = Field(
        default=False,
        description="When true, try Ollama first for tool follow-up even if main response used a different provider.",
    )

    # System prompt override (replaces default; use \\n for newlines in JSON/env)
    system_prompt: str | None = Field(
        default=None,
        description="Override the base system prompt; empty/omit to use default",
    )

    # Ollama: ensure configured models are pulled on startup
    ollama_ensure_models: bool = Field(
        default=False,
        description="On startup, pull any configured Ollama models that are missing",
    )
    provider_retry_count: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Number of retries for transient provider failures (timeout, 429, 503). 0=no retries.",
    )

    # AI providers (multi-endpoint, multi-model) - see docs/CONFIGURATION.md
    ai_providers: dict[str, Any] | None = Field(
        default=None,
        description="Structured config: ollama[], anthropic[], gemini[] with models and notes",
    )
    model_priority: list[dict[str, Any]] | None = Field(
        default=None,
        description="Order to try models: [{provider, instance, model}, ...]",
    )

    # Heartbeat: periodic background tasks
    heartbeat_reflection_minutes: float = Field(
        default=0,
        description="Interval in minutes for self-reflection (question→answer→gregory.md). 0=disabled",
    )
    heartbeat_notes_cleanup_minutes: float = Field(
        default=0,
        description="Interval in minutes for notes cleanup (random doc summarized by advanced model). 0=disabled",
    )
    heartbeat_premium_provider: str = Field(
        default="last",
        description="Which provider to use for premium tasks (cleanup, compression): 'last' (most capable), 'first', or 'ollama'.",
    )

    # Notes
    notes_path: Path = Field(
        default=Path("/app/notes"),
        description="Path to notes directory (mount in Docker)",
    )
    family_members: str = Field(
        default="",
        description="Comma-separated user IDs (e.g. alice,bob,kids)",
    )

    # Memory system (journal files + vector DB)
    memory_enabled: bool = Field(
        default=False,
        description="Enable journal memory system (daily YYYY-MM-DD.md files + ChromaDB vector index)",
    )
    memory_path: Path = Field(
        default=Path("/app/memory"),
        description="Path to memory directory (journal files + ChromaDB data; mount in Docker)",
    )
    memory_similarity_threshold: float = Field(
        default=0.7,
        description="Minimum cosine similarity (0.0-1.0) for a memory to be injected into context",
    )
    memory_top_k: int = Field(
        default=3,
        description="Maximum number of memory results to inject per chat turn",
    )
    memory_embedding_provider: str = Field(
        default="default",
        description="Embedding provider for memory vector index: 'default' (onnxruntime, self-contained) or 'ollama'",
    )
    memory_embedding_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model name (used when memory_embedding_provider='ollama')",
    )

    # Tools (external capabilities)
    wikipedia_enabled: bool = Field(
        default=True,
        description="Enable Wikipedia search via [WIKIPEDIA: query] marker",
    )
    web_search_enabled: bool = Field(
        default=True,
        description="Enable web search via [WEB_SEARCH: query] marker",
    )
    ha_enabled: bool = Field(
        default=False,
        description="Enable Home Assistant integration via [HA_LIST], [HA_STATE], [HA_SERVICE] markers",
    )
    ha_base_url: str | None = Field(
        default=None,
        description="Home Assistant URL (e.g. http://192.168.0.x:8123)",
    )
    ha_access_token: str | None = Field(
        default=None,
        description="Home Assistant long-lived access token",
    )
    fact_check_strict: bool = Field(
        default=True,
        description="Require verification before health, medical, safety, legal, or financial claims",
    )

    # Heartbeat: daily journal summary and monthly compression
    heartbeat_daily_summary_minutes: float = Field(
        default=0,
        description="Interval in minutes for daily journal summary (0=disabled). Suggested: 1440 (once/day).",
    )
    heartbeat_memory_compression_minutes: float = Field(
        default=0,
        description="Interval in minutes for monthly memory compression (0=disabled). Suggested: 10080 (weekly).",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Load from init, JSON file (when not in Docker), .env, then env vars."""
        json_path = Path(os.environ.get("CONFIG_FILE", "config.json"))
        sources: Tuple[PydanticBaseSettingsSource, ...] = (init_settings,)
        if json_path.exists():
            sources = sources + (
                JsonConfigSettingsSource(settings_cls, json_file=json_path),
            )
        return sources + (dotenv_settings, env_settings, file_secret_settings)


def get_config_file_path() -> Path:
    """Path to the JSON config file (used by debug UI)."""
    return Path(os.environ.get("CONFIG_FILE", "config.json"))


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
