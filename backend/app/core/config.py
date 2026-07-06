from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DATABASE_URL = "postgresql+psycopg://lumen:lumen@localhost:5435/lumen"
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Lumen", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    secret_key: str = Field(default="change-me-only-local", alias="SECRET_KEY")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    test_database_url: str = Field(
        default=DEFAULT_TEST_DATABASE_URL,
        validation_alias=AliasChoices("TEST_DATABASE_URL", "LUMEN_TEST_DATABASE_URL"),
    )
    redis_url: str = Field(default="redis://localhost:6382/0", alias="REDIS_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    @field_validator("database_url", "test_database_url")
    @classmethod
    def validate_postgres_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Only postgresql+psycopg URLs are supported.")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
