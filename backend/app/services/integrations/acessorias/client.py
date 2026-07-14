from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.app.core.config import Settings


class AcessoriasConfigurationError(ValueError):
    pass


class AcessoriasAuthenticationError(RuntimeError):
    pass


class AcessoriasRateLimitError(RuntimeError):
    pass


class AcessoriasNotFoundError(RuntimeError):
    pass


class AcessoriasResponseError(RuntimeError):
    pass


class AcessoriasTransportError(RuntimeError):
    pass


class AcessoriasMappingError(RuntimeError):
    pass


class AcessoriasClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: int,
        requests_per_minute: int,
        http_client: httpx.Client | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._requests_per_minute = requests_per_minute
        self._http_client = http_client
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep
        self._last_request_started_at: float | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> "AcessoriasClient":
        if not settings.acessorias_api_base_url:
            raise AcessoriasConfigurationError("ACESSORIAS_API_BASE_URL is required for Acessorias sync.")
        if not settings.acessorias_api_token:
            raise AcessoriasConfigurationError("ACESSORIAS_API_TOKEN is required for Acessorias sync.")
        return cls(
            base_url=settings.acessorias_api_base_url,
            token=settings.acessorias_api_token,
            timeout_seconds=settings.acessorias_timeout_seconds,
            requests_per_minute=settings.acessorias_requests_per_minute,
            http_client=http_client,
            monotonic=monotonic,
            sleep=sleep,
        )

    def get_company(
        self,
        identifier: str,
        *,
        registration_data: bool = False,
        active: str | None = None,
        page: int | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        flags = ["registrationData"] if registration_data else []
        params: dict[str, Any] = {}
        if active is not None:
            params["ativa"] = active
        if page is not None:
            params["Pagina"] = page
        return self._request_json("GET", f"/companies/{identifier}", params=params, flags=flags)

    def iter_companies(self) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            payload = self.get_company("ListAll", registration_data=True, active="S", page=page)
            items = self._coerce_list(payload)
            if not items:
                break
            for item in items:
                yield item
            page += 1

    def get_deliveries(
        self,
        identifier: str,
        *,
        dt_initial: date,
        dt_final: date,
        page: int = 1,
        config: bool = True,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        flags = ["config"] if config else []
        params = {
            "DtInitial": dt_initial.isoformat(),
            "DtFinal": dt_final.isoformat(),
            "Pagina": page,
        }
        return self._request_json("GET", f"/deliveries/{identifier}", params=params, flags=flags)

    def iter_deliveries(self, identifier: str, *, dt_initial: date, dt_final: date) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            payload = self.get_deliveries(identifier, dt_initial=dt_initial, dt_final=dt_final, page=page, config=True)
            items = self._coerce_list(payload)
            if not items:
                break
            for item in items:
                yield item
            page += 1

    def _coerce_list(self, payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        raise AcessoriasResponseError("Unexpected response format from Acessorias.")

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        flags: list[str] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        response = self._request(method, path, params=params, flags=flags)
        if response.status_code == 204:
            return []
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise AcessoriasResponseError("Acessorias returned invalid JSON.") from exc
        if isinstance(payload, dict) and "Erro" in payload:
            raise AcessoriasResponseError(str(payload.get("Erro") or "Acessorias business error."))
        if isinstance(payload, (dict, list)):
            return payload
        raise AcessoriasResponseError("Unexpected response format from Acessorias.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        flags: list[str] | None = None,
    ) -> httpx.Response:
        self._wait_for_rate_limit_slot()
        url = self._build_url(path, params=params or {}, flags=flags or [])
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.Client(timeout=self._timeout_seconds)
        try:
            response = client.request(method, url, headers=self._build_headers(), timeout=self._timeout_seconds)
        except httpx.TimeoutException as exc:
            raise AcessoriasTransportError("Timeout while calling Acessorias API.") from exc
        except httpx.TransportError as exc:
            raise AcessoriasTransportError("Transport error while calling Acessorias API.") from exc
        finally:
            if owns_client:
                client.close()

        if response.status_code == 401:
            raise AcessoriasAuthenticationError("Acessorias authentication failed.")
        if response.status_code == 403:
            raise AcessoriasAuthenticationError("Acessorias access denied.")
        if response.status_code == 404:
            raise AcessoriasNotFoundError("Acessorias resource not found.")
        if response.status_code == 429:
            raise AcessoriasRateLimitError("Acessorias rate limit reached.")
        if response.status_code >= 400:
            raise AcessoriasResponseError(f"Acessorias returned HTTP {response.status_code}.")
        return response

    def _wait_for_rate_limit_slot(self) -> None:
        minimum_interval = 60.0 / float(self._requests_per_minute)
        if self._last_request_started_at is not None:
            elapsed = self._monotonic() - self._last_request_started_at
            remaining = minimum_interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_started_at = self._monotonic()

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }

    def _build_url(self, path: str, *, params: dict[str, Any], flags: list[str]) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        parts: list[str] = []
        if params:
            parts.append(urlencode({key: value for key, value in params.items() if value is not None}))
        if flags:
            parts.append("&".join(flags))
        query = "&".join(part for part in parts if part)
        return f"{self._base_url}{normalized_path}{'?' + query if query else ''}"
