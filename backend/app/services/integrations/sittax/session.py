from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import threading

import httpx

from backend.app.core.config import Settings
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj

from .errors import SittaxSessionError


OBSERVED_COOKIE_DOMAIN = ".sittax.com.br"
OBSERVED_COOKIE_PATH = "/"
OBSERVED_COMPANY_COOKIE = "CnpjDaEmpresaSelecionada"
OBSERVED_OFFICE_COOKIE = "CnpjDoEscritorioSelecionado"
OBSERVED_PERIOD_COOKIE = "DataInicialSelecionada"
OBSERVED_OFFICE_ID_COOKIE = "IdEscritorioSelecionado"
OBSERVED_COMPANY_GROUP_COOKIE = "IdGrupoDeEmpresaSelecionado"


class SittaxSession:
    def __init__(
        self,
        *,
        auth_base_url: str,
        api_base_url: str,
        apuracao_base_url: str,
        timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.auth_base_url = auth_base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")
        self.apuracao_base_url = apuracao_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        self._lock = threading.RLock()
        self._owner_thread_id: int | None = None
        self._exclusive_depth = 0
        self._closed = False
        self._token: str | None = None
        self.office_id: str | None = None
        self.office_name: str | None = None
        self.office_cnpj: str | None = None
        self.user_id: str | None = None
        self.user_role: str | None = None
        self.active_apuracao_company_cnpj: str | None = None
        self.active_apuracao_period: str | None = None
        self.active_api_company_cnpj: str | None = None
        self.active_api_period: str | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
    ) -> "SittaxSession":
        return cls(
            auth_base_url=settings.sittax_auth_base_url,
            api_base_url=settings.sittax_api_base_url,
            apuracao_base_url=settings.sittax_apuracao_base_url,
            timeout_seconds=settings.sittax_timeout_seconds,
            http_client=http_client,
        )

    @property
    def http_client(self) -> httpx.Client:
        self._ensure_open()
        return self._http_client

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def active_company_cnpj(self) -> str | None:
        return self.active_apuracao_company_cnpj

    @property
    def active_period(self) -> str | None:
        return self.active_apuracao_period

    def __enter__(self) -> "SittaxSession":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            "SittaxSession("
            f"auth_base_url={self.auth_base_url!r}, "
            f"api_base_url={self.api_base_url!r}, "
            f"apuracao_base_url={self.apuracao_base_url!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"is_authenticated={self.is_authenticated!r}, "
            f"office_id={'set' if self.office_id else 'unset'}, "
            f"office_cnpj={'set' if self.office_cnpj else 'unset'}, "
            f"active_apuracao_company_cnpj={self.active_apuracao_company_cnpj!r}, "
            f"active_apuracao_period={self.active_apuracao_period!r}, "
            f"active_api_company_cnpj={self.active_api_company_cnpj!r}, "
            f"active_api_period={self.active_api_period!r}, "
            f"closed={self._closed!r})"
        )

    @contextmanager
    def exclusive(self) -> Iterator["SittaxSession"]:
        self._ensure_open()
        thread_id = threading.get_ident()
        self._lock.acquire()
        if self._owner_thread_id == thread_id:
            self._exclusive_depth += 1
        else:
            self._owner_thread_id = thread_id
            self._exclusive_depth = 1
        try:
            yield self
        finally:
            if self._owner_thread_id == thread_id:
                self._exclusive_depth -= 1
                if self._exclusive_depth == 0:
                    self._owner_thread_id = None
            self._lock.release()

    def assert_exclusive(self) -> None:
        if self._owner_thread_id != threading.get_ident():
            raise SittaxSessionError("Sittax session must be used inside session.exclusive().")
        self._ensure_open()

    def mark_authenticated(
        self,
        *,
        token: str,
        office_id: str,
        office_name: str | None,
        office_cnpj: str | None = None,
        user_id: str | None,
        user_role: str | None,
    ) -> None:
        self.assert_exclusive()
        self._token = token
        self.office_id = office_id
        self.office_name = office_name
        self.office_cnpj = normalize_cnpj(office_cnpj)
        self.user_id = user_id
        self.user_role = user_role
        self._http_client.headers["Authorization"] = f"Bearer {token}"
        self._set_cookie(OBSERVED_OFFICE_ID_COOKIE, office_id)
        self._set_cookie(OBSERVED_COMPANY_GROUP_COOKIE, "")
        if self.office_cnpj is not None:
            self._set_cookie(OBSERVED_OFFICE_COOKIE, self.office_cnpj)

    def clear_authentication(self) -> None:
        self.assert_exclusive()
        self._token = None
        self.office_id = None
        self.office_name = None
        self.office_cnpj = None
        self.user_id = None
        self.user_role = None
        self._http_client.headers.pop("Authorization", None)
        self.clear_all_contexts()
        self._delete_cookie(OBSERVED_OFFICE_ID_COOKIE)
        self._delete_cookie(OBSERVED_OFFICE_COOKIE)
        self._delete_cookie(OBSERVED_COMPANY_GROUP_COOKIE)

    def clear_all_contexts(self) -> None:
        self.assert_exclusive()
        self.clear_apuracao_context()
        self.clear_api_context()

    def clear_active_context(self) -> None:
        self.clear_all_contexts()

    def clear_apuracao_context(self) -> None:
        self.assert_exclusive()
        self.active_apuracao_company_cnpj = None
        self.active_apuracao_period = None

    def clear_api_context(self) -> None:
        self.assert_exclusive()
        self.active_api_company_cnpj = None
        self.active_api_period = None
        self._delete_cookie(OBSERVED_COMPANY_COOKIE)
        self._delete_cookie(OBSERVED_PERIOD_COOKIE)

    def set_apuracao_context(self, *, company_cnpj: str, period: str) -> None:
        self.assert_exclusive()
        self.active_apuracao_company_cnpj = company_cnpj
        self.active_apuracao_period = period
        self._set_cookie(OBSERVED_COMPANY_COOKIE, company_cnpj)
        self._set_cookie(OBSERVED_PERIOD_COOKIE, self._cookie_period_value(period))

    def set_api_context(self, *, company_cnpj: str, period: str) -> None:
        self.assert_exclusive()
        self.active_api_company_cnpj = company_cnpj
        self.active_api_period = period
        self._set_cookie(OBSERVED_COMPANY_COOKIE, company_cnpj)
        self._set_cookie(OBSERVED_PERIOD_COOKIE, self._cookie_period_value(period))

    def require_apuracao_context(self, *, company_cnpj: str, period: str) -> None:
        self.assert_exclusive()
        if self.active_apuracao_company_cnpj != company_cnpj or self.active_apuracao_period != period:
            raise SittaxSessionError("Sittax apuracao context does not match the expected company and period.")

    def require_api_context(self, *, company_cnpj: str, period: str) -> None:
        self.assert_exclusive()
        if self.active_api_company_cnpj != company_cnpj or self.active_api_period != period:
            raise SittaxSessionError("Sittax API context does not match the expected company and period.")

    def close(self) -> None:
        if self._closed:
            return
        self._http_client.close()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise SittaxSessionError("Sittax session is closed.")

    def _set_cookie(self, name: str, value: str) -> None:
        self._http_client.cookies.set(
            name,
            value,
            domain=OBSERVED_COOKIE_DOMAIN,
            path=OBSERVED_COOKIE_PATH,
        )

    def _delete_cookie(self, name: str) -> None:
        for domain in (OBSERVED_COOKIE_DOMAIN, OBSERVED_COOKIE_DOMAIN.lstrip("."), None):
            try:
                if domain is None:
                    self._http_client.cookies.delete(name)
                else:
                    self._http_client.cookies.delete(name, domain=domain, path=OBSERVED_COOKIE_PATH)
            except KeyError:
                continue

    @staticmethod
    def _cookie_period_value(period: str) -> str:
        if len(period) != 7 or period[4] != "-":
            raise SittaxSessionError("Sittax cookie period requires YYYY-MM format.")
        return f"{period}-01T00:00:00"
