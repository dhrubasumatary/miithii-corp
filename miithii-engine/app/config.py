"""MIITHII Engine configuration.

Reads the workspace-root .env (gitignored) so one file holds all dev
credentials; environment variables always win over the file.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    service_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
