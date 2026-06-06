"""Project-wide config. Loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    duckdb_path: Path = Field(
        default=REPO_ROOT / "vantage.duckdb",
        alias="VANTAGE_DUCKDB_PATH",
    )
    sec_user_agent: str = Field(
        default="VANTAGE Research contact@example.com",
        alias="SEC_USER_AGENT",
    )
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    model_draft: str = Field(default="claude-opus-4-7", alias="VANTAGE_MODEL_DRAFT")
    model_classify: str = Field(
        default="claude-haiku-4-5-20251001", alias="VANTAGE_MODEL_CLASSIFY"
    )


settings = Settings()
