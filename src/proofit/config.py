"""Application settings loaded from environment variables and `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "proofit.db"  # `data/` is git-ignored


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="PROOFIT_",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
