from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import threading

import httpx

from backend.app.core.config import Settings

from .errors import SittaxSessionError


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
        self.user_id: str | None = None
        self.user_role: str | None = None
        self.active_company_cnpj: str | None = None
        self.active_period: str | None = None

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
            f"active_company_cnpj={self.active_company_cnpj!r}, "
            f"active_period={self.active_period!r}, "
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
        user_id: str | None,
        user_role: str | None,
    ) -> None:
        self.assert_exclusive()
        self._token = token
        self.office_id = office_id
        self.office_name = office_name
        self.user_id = user_id
        self.user_role = user_role
        self._http_client.headers["Authorization"] = f"Bearer {token}"

    def clear_authentication(self) -> None:
        self.assert_exclusive()
        self._token = None
        self.office_id = None
        self.office_name = None
        self.user_id = None
        self.user_role = None
        self._http_client.headers.pop("Authorization", None)

    def close(self) -> None:
        if self._closed:
            return
        self._http_client.close()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise SittaxSessionError("Sittax session is closed.")
