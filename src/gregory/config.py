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

    # Notes
    notes_path: Path = Field(
        default=Path("/app/notes"),
        description="Path to notes directory (mount in Docker)",
    )
    family_members: str = Field(
        default="",
        description="Comma-separated user IDs (e.g. alice,bob,kids)",
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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
