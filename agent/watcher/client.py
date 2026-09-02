"""Sanitized M2M HTTP client for watcher-event metadata."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent.watcher.config import WatcherConfig


@dataclass(frozen=True, slots=True)
class ClientResponse:
    status_code: int | None
    category: str
    body: dict[str, object] | None = None


Transport = Callable[[str, bytes, Mapping[str, str], float], ClientResponse]


class WatcherApiClient:
    def __init__(self, config: WatcherConfig, *, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or _urllib_transport

    def send(self, payload: dict[str, object]) -> ClientResponse:
        if not self._config.agent_token:
            return ClientResponse(None, "AUTH_CONFIGURATION")
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Lumen-Agent-Token": self._config.agent_token}
        return self._transport(
            f"{self._config.api_base_url}/api/v1/lumen/evidences/watcher-event",
            body,
            headers,
            float(self._config.http_timeout_seconds),
        )


def _urllib_transport(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> ClientResponse:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is validated in WatcherConfig.
            return ClientResponse(response.status, _category(response.status), _safe_json(response.read()))
    except HTTPError as exc:
        return ClientResponse(exc.code, _category(exc.code))
    except (TimeoutError, URLError, OSError):
        return ClientResponse(None, "NETWORK_ERROR")


def _category(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "SUCCESS"
    if status_code in {400, 422}:
        return "REJECTED"
    if status_code in {401, 403}:
        return "AUTH_ERROR"
    if status_code == 503:
        return "UNAVAILABLE"
    if 500 <= status_code < 600:
        return "SERVER_ERROR"
    return "REJECTED"


def _safe_json(raw: bytes) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
