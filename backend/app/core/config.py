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
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    initial_admin_email: str | None = Field(default=None, alias="INITIAL_ADMIN_EMAIL")
    initial_admin_password: str | None = Field(default=None, alias="INITIAL_ADMIN_PASSWORD")
    initial_admin_full_name: str | None = Field(default="Initial Admin", alias="INITIAL_ADMIN_FULL_NAME")
    initial_org_name: str | None = Field(default="Lumen", alias="INITIAL_ORG_NAME")
    initial_org_slug: str | None = Field(default="lumen", alias="INITIAL_ORG_SLUG")
    econtrole_api_base_url: str | None = Field(default=None, alias="ECONTROLE_API_BASE_URL")
    econtrole_api_token: str | None = Field(default=None, alias="ECONTROLE_API_TOKEN")
    econtrole_webhook_token: str | None = Field(default=None, alias="ECONTROLE_WEBHOOK_TOKEN")
    econtrole_timeout_seconds: int = Field(default=15, alias="ECONTROLE_TIMEOUT_SECONDS")
    acessorias_api_base_url: str = Field(default="https://api.acessorias.com", alias="ACESSORIAS_API_BASE_URL")
    acessorias_api_token: str | None = Field(default=None, alias="ACESSORIAS_API_TOKEN")
    acessorias_timeout_seconds: int = Field(default=15, alias="ACESSORIAS_TIMEOUT_SECONDS")
    acessorias_requests_per_minute: int = Field(default=100, alias="ACESSORIAS_REQUESTS_PER_MINUTE")

    @field_validator("database_url", "test_database_url")
    @classmethod
    def validate_postgres_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Only postgresql+psycopg URLs are supported.")
        return value

    @field_validator("access_token_expire_minutes", "refresh_token_expire_days")
    @classmethod
    def validate_positive_expiration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Token expiration values must be positive integers.")
        return value

    @field_validator("econtrole_timeout_seconds", "acessorias_timeout_seconds")
    @classmethod
    def validate_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Timeout values must be positive integers.")
        return value

    @field_validator("acessorias_requests_per_minute")
    @classmethod
    def validate_acessorias_rate_limit(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("ACESSORIAS_REQUESTS_PER_MINUTE must be between 1 and 100.")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
