from __future__ import annotations

import calendar
import copy
import json
from pathlib import Path
import re
from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.core.logging import get_logger
from backend.app.core.security import redact_mapping
from backend.app.schemas.sittax import (
    SittaxApuracaoItem,
    SittaxCompanyItem,
    SittaxDifalItem,
    SittaxFiscalDocumentPage,
    SittaxTaskPage,
)
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj

from .errors import (
    SittaxAuthenticationError,
    SittaxAuthorizationError,
    SittaxBusinessError,
    SittaxConfigurationError,
    SittaxContextMismatchError,
    SittaxPaginationError,
    SittaxRateLimitError,
    SittaxResponseError,
    SittaxSessionError,
    SittaxTransportError,
)
from .mapper import (
    map_apuracao_response,
    map_company_item,
    map_difal_response,
    map_fiscal_document_page,
    map_login_response,
    sanitize_contract_message,
    map_task_page,
)
from .session import SittaxSession


logger = get_logger(__name__)
PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
DEFAULT_DOCUMENT_PAGE_SIZE = 15
DEFAULT_TASK_PAGE_SIZE = 25
APP_REFERER = "https://app.sittax.com.br/"


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
            office_cnpj=office.cnpj,
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

    def get_apuracao(self, *, company_cnpj: str, period: str) -> SittaxApuracaoItem:
        self.session.assert_exclusive()
        if not self.session.is_authenticated:
            raise SittaxSessionError("Sittax session is not authenticated.")

        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        observed_period = self._normalize_interface_period(period)
        self.session.clear_apuracao_context()
        self.session.clear_api_context()

        try:
            payload = self._request_json(
                "GET",
                f"{self.session.apuracao_base_url}/api/apuracao/retornar-apuracao-sittax",
                params={"empresaCnpj": normalized_cnpj, "periodo": observed_period},
            )
            mapped = map_apuracao_response(
                payload,
                requested_company_cnpj=normalized_cnpj,
                requested_period=period,
            )
            self.session.set_apuracao_context(
                company_cnpj=mapped.confirmed_company_cnpj or normalized_cnpj,
                period=mapped.confirmed_period,
            )
            return mapped
        except Exception:
            self.session.clear_apuracao_context()
            raise

    def get_difal(self, *, company_cnpj: str, period: str) -> SittaxDifalItem:
        self.session.assert_exclusive()
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        try:
            self.session.require_api_context(company_cnpj=normalized_cnpj, period=period)
        except SittaxSessionError as exc:
            self.session.clear_api_context()
            raise SittaxContextMismatchError(str(exc)) from exc
        payload: dict[str, Any] | None = None
        response: httpx.Response | None = None
        try:
            payload, response = self._request_json_response(
                "GET",
                f"{self.session.api_base_url}/api/difal/obter-valores-difal",
                params={"recalcular": "false"},
            )
            return map_difal_response(payload)
        except Exception as exc:
            self.session.clear_api_context()
            raise self._with_contract_diagnostic(exc, logical_endpoint="difal", payload=payload, response=response)

    def ensure_api_context(self, *, company_cnpj: str, period: str) -> None:
        self.session.assert_exclusive()
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        self.session.require_apuracao_context(company_cnpj=normalized_cnpj, period=period)
        observed_period = self._normalize_interface_period(period)
        payload: dict[str, Any] | None = None
        response: httpx.Response | None = None

        try:
            payload, response = self._request_json_response(
                "POST",
                f"{self.session.api_base_url}/api/v2/painel-contador/valor-auditoria",
                json_body={"periodo": observed_period},
            )
            if payload.get("ok") is not True:
                raise SittaxBusinessError("Sittax API period handoff rejected the selected fiscal period.")
            payload, response = self._request_json_response(
                "GET",
                f"{self.session.api_base_url}/api/painelprincipal/retornar-dados-por-empresa",
            )
            if payload.get("sucesso") is not True:
                raise SittaxContextMismatchError("Sittax API company context could not be confirmed.")
            self.session.set_api_context(company_cnpj=normalized_cnpj, period=period)
        except Exception as exc:
            self.session.clear_api_context()
            raise self._with_contract_diagnostic(
                exc,
                logical_endpoint="api_context_handoff",
                payload=payload,
                response=response,
            )

    def list_fiscal_documents_entry_page(
        self,
        *,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        total: int = 0,
    ) -> SittaxFiscalDocumentPage:
        return self._list_fiscal_documents_page(
            company_cnpj=company_cnpj,
            period=period,
            page_number=page_number,
            page_size=page_size,
            total=total,
            direction="ENTRADA",
            path="/api/nota-fiscal/lista-nota-fiscal-entrada-paginacao",
        )

    def list_fiscal_documents_exit_page(
        self,
        *,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        total: int = 0,
    ) -> SittaxFiscalDocumentPage:
        return self._list_fiscal_documents_page(
            company_cnpj=company_cnpj,
            period=period,
            page_number=page_number,
            page_size=page_size,
            total=total,
            direction="SAIDA",
            path="/api/nota-fiscal/lista-nota-fiscal-saida-paginacao",
        )

    def list_tasks_page(self, *, page_number: int, page_size: int, total: int = 0) -> SittaxTaskPage:
        self.session.assert_exclusive()
        params = None if page_number == 0 and total == 0 else {"pagina": page_number, "pageSize": page_size, "total": total}
        payload, response = self._request_json_response(
            "GET",
            f"{self.session.api_base_url}/api/tarefa/paginacao",
            params=params,
        )
        try:
            return map_task_page(payload, page_number=page_number, page_size=page_size)
        except Exception as exc:
            raise self._with_contract_diagnostic(exc, logical_endpoint="tasks", payload=payload, response=response)

    def paginate_fiscal_documents(
        self,
        *,
        company_cnpj: str,
        period: str,
        direction: str,
        page_size: int = DEFAULT_DOCUMENT_PAGE_SIZE,
        max_pages: int = 100,
    ) -> list[SittaxFiscalDocumentPage]:
        pages: list[SittaxFiscalDocumentPage] = []
        seen_signatures: set[tuple[str, ...]] = set()
        total = 0
        for page_number in range(0, max_pages):
            page = (
                self.list_fiscal_documents_entry_page(
                    company_cnpj=company_cnpj,
                    period=period,
                    page_number=page_number,
                    page_size=page_size,
                    total=total,
                )
                if direction == "ENTRADA"
                else self.list_fiscal_documents_exit_page(
                    company_cnpj=company_cnpj,
                    period=period,
                    page_number=page_number,
                    page_size=page_size,
                    total=total,
                )
            )
            signature = tuple(item.source_document_key for item in page.items)
            if signature in seen_signatures:
                raise SittaxPaginationError("Sittax fiscal document pagination repeated a page.")
            seen_signatures.add(signature)
            pages.append(page)
            total = page.total_filtered or total
            if not page.items:
                break
            if page.total_filtered is not None and (page_number + 1) * page.page_size >= page.total_filtered:
                break
        else:
            raise SittaxPaginationError("Sittax fiscal document pagination reached the defensive page limit.")
        return pages

    def paginate_tasks(self, *, page_size: int = DEFAULT_TASK_PAGE_SIZE, max_pages: int = 100) -> list[SittaxTaskPage]:
        pages: list[SittaxTaskPage] = []
        seen_signatures: set[tuple[str, ...]] = set()
        total = 0
        for page_number in range(0, max_pages):
            page = self.list_tasks_page(page_number=page_number, page_size=page_size, total=total)
            signature = tuple(item.source_task_key for item in page.items)
            if signature in seen_signatures:
                raise SittaxPaginationError("Sittax task pagination repeated a page.")
            seen_signatures.add(signature)
            pages.append(page)
            total = page.total_filtered or total
            if not page.items:
                break
            if page.total_filtered is not None and (page_number + 1) * page.page_size >= page.total_filtered:
                break
        else:
            raise SittaxPaginationError("Sittax task pagination reached the defensive page limit.")
        return pages

    def _list_fiscal_documents_page(
        self,
        *,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        total: int,
        direction: str,
        path: str,
    ) -> SittaxFiscalDocumentPage:
        self.session.assert_exclusive()
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        try:
            self.session.require_api_context(company_cnpj=normalized_cnpj, period=period)
        except SittaxSessionError as exc:
            self.session.clear_api_context()
            raise SittaxContextMismatchError(str(exc)) from exc
        payload: dict[str, Any] | None = None
        response: httpx.Response | None = None
        try:
            payload, response = self._request_json_response(
                "GET",
                f"{self.session.api_base_url}{path}",
                params=self._build_document_params(period=period, page_number=page_number, page_size=page_size, total=total, direction=direction),
            )
            return map_fiscal_document_page(payload, direction=direction, page_number=page_number, page_size=page_size)
        except Exception as exc:
            self.session.clear_api_context()
            raise self._with_contract_diagnostic(exc, logical_endpoint=f"documents_{direction.lower()}", payload=payload, response=response)

    def _request_json_response(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> tuple[dict[str, Any], httpx.Response]:
        response = self._request(method, url, params=params, json_body=json_body, include_auth=include_auth)
        payload = self._parse_json_response(response)
        return payload, response

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
        return self._parse_json_response(response)

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise SittaxResponseError("Sittax returned invalid JSON.") from exc
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise SittaxResponseError("Sittax returned invalid nested JSON.") from exc
        if not isinstance(payload, dict):
            raise SittaxResponseError("Unexpected Sittax response format.")
        return payload

    def _with_contract_diagnostic(
        self,
        exc: Exception,
        *,
        logical_endpoint: str,
        payload: dict[str, Any] | None,
        response: httpx.Response | None,
    ) -> Exception:
        if not isinstance(exc, (SittaxResponseError, SittaxBusinessError, SittaxContextMismatchError)):
            return exc
        diagnostic = self.build_contract_diagnostic(
            logical_endpoint=logical_endpoint,
            payload=payload,
            response=response,
        )
        return exc.__class__(str(exc), diagnostic=diagnostic)

    def build_contract_diagnostic(
        self,
        *,
        logical_endpoint: str,
        payload: dict[str, Any] | None,
        response: httpx.Response | None,
    ) -> dict[str, Any]:
        top_level_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
        data_candidate = payload.get("data") if isinstance(payload, dict) else None
        lista_candidate = payload.get("lista") if isinstance(payload, dict) else None
        difal_candidate = payload.get("difal") if isinstance(payload, dict) else None
        sent_cookie_names = sorted(cookie.name for cookie in self.session.http_client.cookies.jar)
        received_cookie_names = sorted(cookie.name for cookie in response.cookies.jar) if response is not None else []
        items_count = len(lista_candidate) if isinstance(lista_candidate, list) else None
        if items_count is None and isinstance(data_candidate, list):
            items_count = len(data_candidate)
        return {
            "logical_endpoint": logical_endpoint,
            "host": response.request.url.host if response is not None else None,
            "http_status": response.status_code if response is not None else None,
            "content_type": response.headers.get("content-type") if response is not None else None,
            "top_level_type": type(payload).__name__ if payload is not None else None,
            "top_level_keys": top_level_keys,
            "business_code": self._first_present(payload, "codigo", "code", "status"),
            "success_flag": self._first_present(payload, "sucesso", "success", "ok"),
            "message_sanitized": sanitize_contract_message(self._first_present(payload, "mensagem", "message")),
            "data_type": (
                "list"
                if isinstance(data_candidate, list)
                else "dict"
                if isinstance(data_candidate, dict)
                else "list"
                if isinstance(lista_candidate, list)
                else "dict"
                if isinstance(difal_candidate, dict)
                else None
            ),
            "items_count": items_count,
            "cookie_names_sent": sent_cookie_names,
            "cookie_names_received": received_cookie_names,
            "context_state_before": {
                "apuracao_company_context_present": self.session.active_apuracao_company_cnpj is not None,
                "apuracao_period_context_present": self.session.active_apuracao_period is not None,
                "api_company_context_present": self.session.active_api_company_cnpj is not None,
                "api_period_context_present": self.session.active_api_period is not None,
            },
            "context_state_after": {
                "apuracao_company_context_present": self.session.active_apuracao_company_cnpj is not None,
                "apuracao_period_context_present": self.session.active_apuracao_period is not None,
                "api_company_context_present": self.session.active_api_company_cnpj is not None,
                "api_period_context_present": self.session.active_api_period is not None,
            },
        }

    @staticmethod
    def _first_present(payload: dict[str, Any] | None, *keys: str) -> Any:
        if payload is None:
            return None
        for key in keys:
            if key in payload:
                return payload.get(key)
        return None

    @staticmethod
    def _build_document_params(
        *,
        period: str,
        page_number: int,
        page_size: int,
        total: int,
        direction: str,
    ) -> dict[str, Any]:
        year = int(period[:4])
        month = int(period[5:7])
        last_day = calendar.monthrange(year, month)[1]
        period_filter = f"01-{month:02d}-{year:04d} {last_day:02d}-{month:02d}-{year:04d}[OR]"
        if direction == "ENTRADA":
            filtros = f"DataEntrada={period_filter}"
            ordenacao = "DataEntrada[ASC]"
        else:
            filtros = f"DataCompetencia={period_filter}"
            ordenacao = "DataEmissao[ASC]"
        return {
            "pagina": page_number,
            "pageSize": page_size,
            "filtros": filtros,
            "ordenacao": ordenacao,
            "total": total,
        }

    @staticmethod
    def _normalize_company_cnpj(company_cnpj: str) -> str:
        normalized = normalize_cnpj(company_cnpj)
        if normalized is None or len(normalized) != 14 or not normalized.isdigit():
            raise SittaxResponseError("Sittax apuracao requires a valid company cnpj.")
        return normalized

    @staticmethod
    def _normalize_interface_period(period: str) -> str:
        if period != period.strip() or not PERIOD_RE.fullmatch(period):
            raise SittaxResponseError("Sittax apuracao requires period in YYYY-MM format.")
        year = int(period[:4])
        month = int(period[5:7])
        if month < 1 or month > 12:
            raise SittaxResponseError("Sittax apuracao requires a valid period month.")
        return f"{month:02d}/{year:04d}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": APP_REFERER,
        }
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
        apuracao_payload: dict[str, Any] | None = None,
        difal_payload: dict[str, Any] | None = None,
        entry_documents_payload: dict[str, Any] | None = None,
        exit_documents_payload: dict[str, Any] | None = None,
        tasks_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(session=session)
        self._login_payload = login_payload
        self._companies_payload = companies_payload
        self._apuracao_payload = apuracao_payload
        self._difal_payload = difal_payload
        self._entry_documents_payload = entry_documents_payload
        self._exit_documents_payload = exit_documents_payload
        self._tasks_payload = tasks_payload

    @classmethod
    def from_files(
        cls,
        *,
        login_path: str | Path,
        companies_path: str | Path,
        apuracao_path: str | Path | None = None,
        difal_path: str | Path | None = None,
        entry_documents_path: str | Path | None = None,
        exit_documents_path: str | Path | None = None,
        tasks_path: str | Path | None = None,
        session: SittaxSession,
    ) -> "FixtureSittaxClient":
        return cls(
            session=session,
            login_payload=json.loads(Path(login_path).read_text(encoding="utf-8")),
            companies_payload=json.loads(Path(companies_path).read_text(encoding="utf-8")),
            apuracao_payload=(
                json.loads(Path(apuracao_path).read_text(encoding="utf-8")) if apuracao_path is not None else None
            ),
            difal_payload=json.loads(Path(difal_path).read_text(encoding="utf-8")) if difal_path is not None else None,
            entry_documents_payload=(
                json.loads(Path(entry_documents_path).read_text(encoding="utf-8"))
                if entry_documents_path is not None
                else None
            ),
            exit_documents_payload=(
                json.loads(Path(exit_documents_path).read_text(encoding="utf-8"))
                if exit_documents_path is not None
                else None
            ),
            tasks_payload=json.loads(Path(tasks_path).read_text(encoding="utf-8")) if tasks_path is not None else None,
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
            office_cnpj=office.cnpj,
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

    def get_apuracao(self, *, company_cnpj: str, period: str) -> SittaxApuracaoItem:
        self.session.assert_exclusive()
        if not self.session.is_authenticated:
            raise SittaxSessionError("Sittax session is not authenticated.")
        if self._apuracao_payload is None:
            raise SittaxResponseError("Sittax apuracao fixture payload is not configured.")

        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        self._normalize_interface_period(period)
        self.session.clear_all_contexts()
        try:
            payload = copy.deepcopy(self._apuracao_payload)
            self._adapt_apuracao_fixture(payload=payload, company_cnpj=normalized_cnpj, period=period)
            mapped = map_apuracao_response(
                payload,
                requested_company_cnpj=normalized_cnpj,
                requested_period=period,
            )
            self.session.set_apuracao_context(
                company_cnpj=mapped.confirmed_company_cnpj or normalized_cnpj,
                period=mapped.confirmed_period,
            )
            return mapped
        except Exception:
            self.session.clear_all_contexts()
            raise

    def ensure_api_context(self, *, company_cnpj: str, period: str) -> None:
        self.session.assert_exclusive()
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        self.session.require_apuracao_context(company_cnpj=normalized_cnpj, period=period)
        self.session.set_api_context(company_cnpj=normalized_cnpj, period=period)

    def get_difal(self, *, company_cnpj: str, period: str) -> SittaxDifalItem:
        self.session.assert_exclusive()
        if self._difal_payload is None:
            raise SittaxResponseError("Sittax DIFAL fixture payload is not configured.")
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        try:
            self.session.require_api_context(company_cnpj=normalized_cnpj, period=period)
        except SittaxSessionError as exc:
            self.session.clear_api_context()
            raise SittaxContextMismatchError(str(exc)) from exc
        return map_difal_response(copy.deepcopy(self._difal_payload))

    def list_fiscal_documents_entry_page(
        self,
        *,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        total: int = 0,
    ) -> SittaxFiscalDocumentPage:
        del total
        return self._fixture_document_page(
            payload=self._entry_documents_payload,
            company_cnpj=company_cnpj,
            period=period,
            page_number=page_number,
            page_size=page_size,
            direction="ENTRADA",
        )

    def list_fiscal_documents_exit_page(
        self,
        *,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        total: int = 0,
    ) -> SittaxFiscalDocumentPage:
        del total
        return self._fixture_document_page(
            payload=self._exit_documents_payload,
            company_cnpj=company_cnpj,
            period=period,
            page_number=page_number,
            page_size=page_size,
            direction="SAIDA",
        )

    def list_tasks_page(self, *, page_number: int, page_size: int, total: int = 0) -> SittaxTaskPage:
        del total
        self.session.assert_exclusive()
        if self._tasks_payload is None:
            raise SittaxResponseError("Sittax task fixture payload is not configured.")
        return map_task_page(copy.deepcopy(self._tasks_payload), page_number=page_number, page_size=page_size)

    def _fixture_document_page(
        self,
        *,
        payload: dict[str, Any] | None,
        company_cnpj: str,
        period: str,
        page_number: int,
        page_size: int,
        direction: str,
    ) -> SittaxFiscalDocumentPage:
        self.session.assert_exclusive()
        if payload is None:
            raise SittaxResponseError("Sittax fiscal document fixture payload is not configured.")
        normalized_cnpj = self._normalize_company_cnpj(company_cnpj)
        try:
            self.session.require_api_context(company_cnpj=normalized_cnpj, period=period)
        except SittaxSessionError as exc:
            self.session.clear_api_context()
            raise SittaxContextMismatchError(str(exc)) from exc
        return map_fiscal_document_page(copy.deepcopy(payload), direction=direction, page_number=page_number, page_size=page_size)

    @staticmethod
    def _adapt_apuracao_fixture(*, payload: dict[str, Any], company_cnpj: str, period: str) -> None:
        data = payload.get("data")
        if not isinstance(data, dict):
            return
        data["empresaCnpj"] = company_cnpj
        company_name = data.get("empresaNome")
        if isinstance(data.get("periodoFiscal"), dict):
            data["periodoFiscal"]["dataInicial"] = f"{period}-01T00:00:00"
            data["periodoFiscal"]["dataFinal"] = f"{period}-28T23:59:59.999"
        else:
            data["periodoFiscal"] = f"{period[5:7]}/{period[:4]}"
        companies = data.get("empresasApuracao")
        if isinstance(companies, list):
            for company in companies:
                if not isinstance(company, dict):
                    continue
                company["cnpj"] = company_cnpj
                if company_name and company.get("nome") is None:
                    company["nome"] = company_name
