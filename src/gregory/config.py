"""Configuration via environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
