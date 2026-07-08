from __future__ import annotations

from typing import Any

import httpx

from backend.app.core.config import Settings


ECONTROLE_COMPANIES_PATH = "/companies"


class EControleClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: int = 15,
        companies_path: str = ECONTROLE_COMPANIES_PATH,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._companies_path = companies_path
        self._http_client = http_client

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        companies_path: str = ECONTROLE_COMPANIES_PATH,
    ) -> "EControleClient":
        if not settings.econtrole_api_base_url:
            raise ValueError("ECONTROLE_API_BASE_URL is required for eControle sync.")
        if not settings.econtrole_api_token:
            raise ValueError("ECONTROLE_API_TOKEN is required for eControle sync.")

        return cls(
            base_url=settings.econtrole_api_base_url,
            token=settings.econtrole_api_token,
            timeout_seconds=settings.econtrole_timeout_seconds,
            companies_path=companies_path,
            http_client=http_client,
        )

    def list_companies(self) -> list[dict[str, Any]]:
        response = self._request("GET", self._companies_path)
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("items", "results", "companies", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        raise ValueError("Unexpected eControle companies response format.")

    def _request(self, method: str, path: str) -> httpx.Response:
        if self._http_client is not None:
            response = self._http_client.request(
                method,
                self._build_url(path),
                headers=self._build_headers(),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            return response

        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.request(
                method,
                self._build_url(path),
                headers=self._build_headers(),
            )
            response.raise_for_status()
            return response

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{normalized_path}"

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
