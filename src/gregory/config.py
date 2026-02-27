"""Configuration via environment variables and optional JSON file."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Tuple, Type

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
