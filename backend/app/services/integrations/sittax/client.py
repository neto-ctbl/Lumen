from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.core.logging import get_logger
from backend.app.core.security import redact_mapping
from backend.app.schemas.sittax import SittaxCompanyItem

from .errors import (
    SittaxAuthenticationError,
    SittaxAuthorizationError,
    SittaxConfigurationError,
    SittaxRateLimitError,
    SittaxResponseError,
    SittaxSessionError,
    SittaxTransportError,
)
from .mapper import map_company_item, map_login_response
from .session import SittaxSession


logger = get_logger(__name__)


class SittaxClient:
    def __init__(self, *, session: SittaxSession) -> None:
        self.session = session

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        session: SittaxSession | None = None,
        http_client: httpx.Client | None = None,
    ) -> "SittaxClient":
        return cls(session=session or SittaxSession.from_settings(settings, http_client=http_client))

    def __repr__(self) -> str:
        return f"SittaxClient(session={self.session!r})"

    def close(self) -> None:
        self.session.close()

    def authenticate_with_settings(self, settings: Settings) -> None:
        if not settings.sittax_email:
            raise SittaxConfigurationError("SITTAX_EMAIL is required for real Sittax authentication.")
        if not settings.sittax_password:
            raise SittaxConfigurationError("SITTAX_PASSWORD is required for real Sittax authentication.")
        self.authenticate(username=settings.sittax_email, password=settings.sittax_password)

    def authenticate(self, *, username: str, password: str) -> None:
        self.session.assert_exclusive()
        if self.session.is_authenticated:
            return
        if not username:
            raise SittaxConfigurationError("Sittax username is required.")
        if not password:
            raise SittaxConfigurationError("Sittax password is required.")

        logger.info("sittax login started")
        payload = self._request_json(
            "POST",
            f"{self.session.auth_base_url}/api/auth/login",
            json_body={"usuario": username, "senha": password},
            include_auth=False,
        )
        mapped = map_login_response(payload)
        office = mapped["office"]
        self.session.mark_authenticated(
            token=mapped["token"],
            office_id=office.id,
            office_name=office.name,
            user_id=mapped["user_id"],
            user_role=mapped["user_role"],
        )
        logger.info("sittax login succeeded")

    def list_companies_payloads(self) -> list[dict[str, Any]]:
        self.session.assert_exclusive()
        if not self.session.is_authenticated or not self.session.office_id:
            raise SittaxSessionError("Sittax session is not authenticated.")

        payload = self._request_json(
            "GET",
            f"{self.session.api_base_url}/api/empresa/listar-todas-escritorio-empresas-selecao",
            params={"idEscritorio": self.session.office_id},
        )
        companies = payload.get("empresas")
        if payload.get("sucesso") is not True:
            raise SittaxResponseError("Sittax companies response returned sucesso=false.")
        if not isinstance(companies, list):
            raise SittaxResponseError("Sittax companies response is missing empresas list.")
        normalized: list[dict[str, Any]] = []
        for entry in companies:
            if not isinstance(entry, dict):
                raise SittaxResponseError("Sittax companies payload contains a non-object company entry.")
            normalized.append(entry)
        logger.info("sittax companies request succeeded", count=len(normalized))
        return normalized

    def list_companies(self) -> list[SittaxCompanyItem]:
        return [map_company_item(payload) for payload in self.list_companies_payloads()]

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> dict[str, Any]:
        response = self._request(method, url, params=params, json_body=json_body, include_auth=include_auth)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SittaxResponseError("Sittax returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise SittaxResponseError("Unexpected Sittax response format.")
        return payload

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if include_auth and self.session.is_authenticated:
            # The session client keeps the current bearer token in memory-only headers.
            pass
        try:
            response = self.session.http_client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.session.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise SittaxTransportError("Timeout while calling Sittax.") from exc
        except httpx.TransportError as exc:
            raise SittaxTransportError("Transport error while calling Sittax.") from exc

        if response.status_code == 401:
            raise SittaxAuthenticationError("Sittax authentication failed.")
        if response.status_code == 403:
            raise SittaxAuthorizationError("Sittax access denied.")
        if response.status_code == 429:
            raise SittaxRateLimitError("Sittax rate limit reached.")
        if response.status_code >= 400:
            raise SittaxResponseError(f"Sittax returned HTTP {response.status_code}.")

        return response

    @staticmethod
    def sanitize_external_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return redact_mapping(payload)


class FixtureSittaxClient(SittaxClient):
    def __init__(
        self,
        *,
        session: SittaxSession,
        login_payload: dict[str, Any],
        companies_payload: dict[str, Any],
    ) -> None:
        super().__init__(session=session)
        self._login_payload = login_payload
        self._companies_payload = companies_payload

    @classmethod
    def from_files(
        cls,
        *,
        login_path: str | Path,
        companies_path: str | Path,
        session: SittaxSession,
    ) -> "FixtureSittaxClient":
        return cls(
            session=session,
            login_payload=json.loads(Path(login_path).read_text(encoding="utf-8")),
            companies_payload=json.loads(Path(companies_path).read_text(encoding="utf-8")),
        )

    def authenticate(self, *, username: str, password: str) -> None:
        del username, password
        self.session.assert_exclusive()
        if self.session.is_authenticated:
            return
        mapped = map_login_response(self._login_payload)
        office = mapped["office"]
        self.session.mark_authenticated(
            token=mapped["token"],
            office_id=office.id,
            office_name=office.name,
            user_id=mapped["user_id"],
            user_role=mapped["user_role"],
        )

    def authenticate_with_settings(self, settings: Settings) -> None:
        del settings
        self.authenticate(username="fixture", password="fixture")

    def list_companies_payloads(self) -> list[dict[str, Any]]:
        self.session.assert_exclusive()
        if not self.session.is_authenticated:
            raise SittaxSessionError("Sittax session is not authenticated.")
        companies = self._companies_payload.get("empresas")
        if self._companies_payload.get("sucesso") is not True:
            raise SittaxResponseError("Sittax companies response returned sucesso=false.")
        if not isinstance(companies, list):
            raise SittaxResponseError("Sittax companies response is missing empresas list.")
        return [item for item in companies if isinstance(item, dict)]

    def list_companies(self) -> list[SittaxCompanyItem]:
        return [map_company_item(payload) for payload in self.list_companies_payloads()]
