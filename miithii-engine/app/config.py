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

    database_url: str | None = None  # runtime = miithii_app role (RLS-enforced)
    database_url_admin: str | None = None  # migrations/provisioning (postgres role)

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.1-flash-lite"
    openrouter_api_key: str | None = None  # alt adapter, not prod PII
    aimlapi_api_key: str | None = None  # adapter chain primary (paid aggregator)
    aimlapi_model: str = "google/gemini-flash-latest"
    aimlapi_base_url: str = "https://api.aimlapi.com/v1"
    aimlapi_timeout_s: float = 60.0
    classifier_confidence_threshold: float = 0.6
    draft_timeout_s: float = 45.0
    embedding_model: str = "gemini-embedding-001"  # text-embedding-004 was retired from the API
    force_deterministic: bool = False  # tests/evals: no network, no cost
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    service_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
