from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_DATABASE_URL = "postgresql+psycopg://lumen:lumen@localhost:5435/lumen"
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test"
TRACKED_ENV_VARS = (
    "APP_NAME",
    "APP_ENV",
    "APP_DEBUG",
    "API_HOST",
    "API_PORT",
    "SECRET_KEY",
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "LUMEN_TEST_DATABASE_URL",
    "REDIS_URL",
    "LOG_LEVEL",
    "LOG_JSON",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "INITIAL_ADMIN_EMAIL",
    "INITIAL_ADMIN_PASSWORD",
    "INITIAL_ADMIN_FULL_NAME",
    "INITIAL_ORG_NAME",
    "INITIAL_ORG_SLUG",
    "ECONTROLE_API_BASE_URL",
    "ECONTROLE_API_TOKEN",
    "ECONTROLE_WEBHOOK_TOKEN",
    "ECONTROLE_TIMEOUT_SECONDS",
    "ACESSORIAS_API_BASE_URL",
    "ACESSORIAS_API_TOKEN",
    "ACESSORIAS_TIMEOUT_SECONDS",
    "ACESSORIAS_REQUESTS_PER_MINUTE",
    "SITTAX_AUTH_BASE_URL",
    "SITTAX_API_BASE_URL",
    "SITTAX_APURACAO_BASE_URL",
    "SITTAX_EMAIL",
    "SITTAX_PASSWORD",
    "SITTAX_API_TOKEN",
    "SITTAX_TIMEOUT_SECONDS",
    "ECONET_BASE_URL",
    "ECONET_TIMEOUT_SECONDS",
    "ECONET_ASSISTED_SESSION_ENABLED",
    "ECONET_SESSION_MAX_AGE_MINUTES",
    "ECONET_ENRICH_DEFAULT_LIMIT",
    "ECONET_ENRICH_MAX_LIMIT",
    "ECONET_ENRICH_REQUEST_DELAY_SECONDS",
    "LUMEN_DISABLE_DOTENV",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
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
    sittax_auth_base_url: str = Field(default="https://autenticacao.sittax.com.br", alias="SITTAX_AUTH_BASE_URL")
    sittax_api_base_url: str = Field(default="https://api.sittax.com.br", alias="SITTAX_API_BASE_URL")
    sittax_apuracao_base_url: str = Field(
        default="https://apuracao.sittax.com.br",
        alias="SITTAX_APURACAO_BASE_URL",
    )
    sittax_email: str | None = Field(default=None, alias="SITTAX_EMAIL")
    sittax_password: str | None = Field(default=None, alias="SITTAX_PASSWORD")
    sittax_api_token: str | None = Field(default=None, alias="SITTAX_API_TOKEN")
    sittax_timeout_seconds: int = Field(default=20, alias="SITTAX_TIMEOUT_SECONDS")
    econet_base_url: str = Field(default="https://www.econeteditora.com.br", alias="ECONET_BASE_URL")
    econet_timeout_seconds: int = Field(default=20, alias="ECONET_TIMEOUT_SECONDS")
    econet_assisted_session_enabled: bool = Field(default=False, alias="ECONET_ASSISTED_SESSION_ENABLED")
    econet_session_max_age_minutes: int = Field(default=480, alias="ECONET_SESSION_MAX_AGE_MINUTES")
    econet_enrich_default_limit: int = Field(default=5, alias="ECONET_ENRICH_DEFAULT_LIMIT")
    econet_enrich_max_limit: int = Field(default=50, alias="ECONET_ENRICH_MAX_LIMIT")
    econet_enrich_request_delay_seconds: float = Field(default=0.5, alias="ECONET_ENRICH_REQUEST_DELAY_SECONDS")

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

    @field_validator(
        "econtrole_timeout_seconds",
        "acessorias_timeout_seconds",
        "sittax_timeout_seconds",
        "econet_timeout_seconds",
        "econet_session_max_age_minutes",
        "econet_enrich_default_limit",
        "econet_enrich_max_limit",
    )
    @classmethod
    def validate_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Timeout values must be positive integers.")
        return value

    @field_validator("econet_enrich_request_delay_seconds")
    @classmethod
    def validate_econet_delay(cls, value: float) -> float:
        if value < 0:
            raise ValueError("ECONET_ENRICH_REQUEST_DELAY_SECONDS must be non-negative.")
        return value

    @field_validator("acessorias_requests_per_minute")
    @classmethod
    def validate_acessorias_rate_limit(cls, value: int) -> int:
        if value < 1 or value > 100:
            raise ValueError("ACESSORIAS_REQUESTS_PER_MINUTE must be between 1 and 100.")
        return value

    @field_validator("econet_base_url")
    @classmethod
    def validate_econet_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https":
            raise ValueError("ECONET_BASE_URL must use HTTPS.")
        if parts.hostname != "www.econeteditora.com.br":
            raise ValueError("ECONET_BASE_URL must target www.econeteditora.com.br.")
        if parts.username or parts.password:
            raise ValueError("ECONET_BASE_URL must not contain embedded credentials.")
        if parts.query or parts.fragment:
            raise ValueError("ECONET_BASE_URL must not contain query string or fragment.")
        if parts.path.rstrip("/"):
            raise ValueError("ECONET_BASE_URL must not contain a path.")
        return f"{parts.scheme}://{parts.netloc}"


def _tracked_env_snapshot() -> tuple[tuple[str, str | None], ...]:
    return tuple((name, os.getenv(name)) for name in TRACKED_ENV_VARS)


def _env_file_state() -> tuple[str | None, int | None]:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None, None
    stat = env_path.stat()
    return str(env_path), stat.st_mtime_ns


@lru_cache(maxsize=8)
def _load_settings_cached(
    *,
    disable_dotenv: bool,
    env_file_path: str | None,
    env_file_mtime_ns: int | None,
    env_snapshot: tuple[tuple[str, str | None], ...],
) -> Settings:
    if disable_dotenv:
        return Settings(_env_file=None)
    return Settings()


def get_settings() -> Settings:
    disable_dotenv = os.getenv("LUMEN_DISABLE_DOTENV") == "1"
    env_file_path, env_file_mtime_ns = (None, None) if disable_dotenv else _env_file_state()
    return _load_settings_cached(
        disable_dotenv=disable_dotenv,
        env_file_path=env_file_path,
        env_file_mtime_ns=env_file_mtime_ns,
        env_snapshot=_tracked_env_snapshot(),
    )


def _clear_settings_cache() -> None:
    _load_settings_cached.cache_clear()


get_settings.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
