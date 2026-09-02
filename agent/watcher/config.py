"""Local configuration for the operational fiscal watcher."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


DEFAULT_WATCHER_ROOT = Path(r"G:\EMPRESAS")
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_SCAN_INTERVAL_SECONDS = 15
DEFAULT_STABLE_SECONDS = 5
DEFAULT_HTTP_TIMEOUT_SECONDS = 15
DEFAULT_STATE_PATH = Path("agent/.state/watcher_state.json")
DEFAULT_HEALTH_PATH = Path("agent/.state/watcher_health.json")


@dataclass(frozen=True, slots=True)
class WatcherConfig:
    root: Path = DEFAULT_WATCHER_ROOT
    api_base_url: str = DEFAULT_API_BASE_URL
    agent_token: str = field(default="", repr=False)
    scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS
    stable_seconds: int = DEFAULT_STABLE_SECONDS
    http_timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS
    state_path: Path = DEFAULT_STATE_PATH
    health_path: Path = DEFAULT_HEALTH_PATH

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "WatcherConfig":
        source = os.environ if environ is None else environ
        api_base_url = source.get("LUMEN_WATCHER_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
        _validate_api_base_url(api_base_url)
        return cls(
            root=Path(source.get("LUMEN_WATCHER_ROOT", str(DEFAULT_WATCHER_ROOT))),
            api_base_url=api_base_url,
            agent_token=source.get("LUMEN_WATCHER_AGENT_TOKEN", ""),
            scan_interval_seconds=_positive_int(source, "LUMEN_WATCHER_SCAN_INTERVAL_SECONDS", DEFAULT_SCAN_INTERVAL_SECONDS),
            stable_seconds=_positive_int(source, "LUMEN_WATCHER_STABLE_SECONDS", DEFAULT_STABLE_SECONDS, allow_zero=True),
            http_timeout_seconds=_positive_int(source, "LUMEN_WATCHER_HTTP_TIMEOUT_SECONDS", DEFAULT_HTTP_TIMEOUT_SECONDS),
            state_path=Path(source.get("LUMEN_WATCHER_STATE_PATH", str(DEFAULT_STATE_PATH))),
            health_path=Path(source.get("LUMEN_WATCHER_HEALTH_PATH", str(DEFAULT_HEALTH_PATH))),
        )


def _positive_int(source: Mapping[str, str], name: str, default: int, *, allow_zero: bool = False) -> int:
    try:
        value = int(source.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be positive")
    return value


def _validate_api_base_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("LUMEN_WATCHER_API_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.scheme == "http" and parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("remote watcher API URLs must use HTTPS")
