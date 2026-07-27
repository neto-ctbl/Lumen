from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import threading
from typing import Any

import httpx

from backend.app.core.config import Settings, get_settings
from backend.app.core.enums import EconetSessionStatus

from .errors import (
    EconetSessionDisabledError,
    EconetSessionExpiredError,
    EconetSessionInvalidError,
    EconetSessionNotLoadedError,
)


ALLOWED_COOKIE_DOMAINS = {".econeteditora.com.br", "www.econeteditora.com.br"}
ALLOWED_COOKIE_NAMES = {
    "bG0naW4",
    "bG9naW4",
    "cookiesession1",
    "operacional",
    "PHPSESSID",
    "usuariocopia",
    "spy_copia",
    "cross-site-cookie",
}
ANALYTICS_COOKIE_PREFIXES = ("_ga", "_hj")
MAX_COOKIE_BYTES = 4096
MAX_COOKIE_COUNT = 32


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EconetAssistedSession:
    def __init__(self, *, enabled: bool, max_age_minutes: int) -> None:
        self._lock = threading.RLock()
        self._enabled = enabled
        self._max_age_minutes = max_age_minutes
        self._cookies: list[dict[str, Any]] = []
        self._status = EconetSessionStatus.NOT_LOADED if enabled else EconetSessionStatus.DISABLED
        self._loaded_at: datetime | None = None
        self._validated_at: datetime | None = None
        self._expires_at: datetime | None = None
        self._last_error_kind: str | None = None
        self._generation = 0

    def __repr__(self) -> str:
        snapshot = self.snapshot()
        return (
            "EconetAssistedSession("
            f"status={snapshot['status']!r}, "
            f"cookie_count={snapshot['cookie_count']!r}, "
            f"cookie_names={snapshot['cookie_names']!r}, "
            f"generation={snapshot['generation']!r})"
        )

    def configure(self, *, enabled: bool, max_age_minutes: int) -> None:
        with self._lock:
            self._enabled = enabled
            self._max_age_minutes = max_age_minutes
            if not enabled:
                self._status = EconetSessionStatus.DISABLED
            elif not self._cookies and self._status not in {
                EconetSessionStatus.EXPIRED,
                EconetSessionStatus.INVALID,
                EconetSessionStatus.ERROR,
            }:
                self._status = EconetSessionStatus.NOT_LOADED
            elif self._status == EconetSessionStatus.DISABLED:
                self._status = EconetSessionStatus.LOADED_UNVALIDATED
            self._refresh_expiration_locked()

    @contextmanager
    def exclusive(self) -> Iterator["EconetAssistedSession"]:
        with self._lock:
            self._refresh_expiration_locked()
            yield self

    def import_storage_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._assert_enabled_locked()
            if not isinstance(payload, dict):
                raise EconetSessionInvalidError("Econet session import requires a JSON object.")
            for forbidden_key in ("origins", "localStorage", "sessionStorage", "indexedDB", "token"):
                if forbidden_key in payload:
                    raise EconetSessionInvalidError(f"Econet session import does not accept {forbidden_key}.")
            cookies = payload.get("cookies")
            if not isinstance(cookies, list) or not cookies:
                raise EconetSessionInvalidError("Econet session import requires a non-empty cookies list.")
            if len(cookies) > MAX_COOKIE_COUNT:
                raise EconetSessionInvalidError("Econet session import exceeded the defensive cookie limit.")

            normalized: list[dict[str, Any]] = []
            seen: dict[tuple[str, str, str], str] = {}
            analytics_seen = 0
            for item in cookies:
                if not isinstance(item, dict):
                    raise EconetSessionInvalidError("Econet session import cookies must be objects.")
                cookie = self._normalize_cookie(item)
                if cookie is None:
                    analytics_seen += 1
                    continue
                key = (cookie["name"], cookie["domain"], cookie["path"])
                previous_value = seen.get(key)
                if previous_value is not None and previous_value != cookie["value"]:
                    raise EconetSessionInvalidError("Econet session import contains conflicting duplicate cookies.")
                seen[key] = cookie["value"]
                normalized.append(cookie)

            if not normalized:
                if analytics_seen:
                    raise EconetSessionInvalidError("Econet session import contained only analytics cookies.")
                raise EconetSessionInvalidError("Econet session import did not contain allowlisted cookies.")

            self._cookies = normalized
            self._status = EconetSessionStatus.LOADED_UNVALIDATED
            self._loaded_at = _utcnow()
            self._validated_at = None
            self._expires_at = self._loaded_at + timedelta(minutes=self._max_age_minutes)
            self._last_error_kind = None
            self._generation += 1
            return self.snapshot()

    def build_cookie_jar(self) -> httpx.Cookies:
        with self._lock:
            self._assert_enabled_locked()
            self._assert_loaded_locked()
            jar = httpx.Cookies()
            for cookie in self._cookies:
                jar.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie["domain"],
                    path=cookie["path"],
                )
            return jar

    def mark_valid(self) -> dict[str, Any]:
        with self._lock:
            self._assert_enabled_locked()
            self._assert_loaded_locked()
            observed_at = _utcnow()
            self._status = EconetSessionStatus.VALID
            self._validated_at = observed_at
            self._expires_at = observed_at + timedelta(minutes=self._max_age_minutes)
            self._last_error_kind = None
            return self.snapshot()

    def mark_expired(self, error_kind: str = "session_expired") -> dict[str, Any]:
        with self._lock:
            self._status = EconetSessionStatus.EXPIRED if self._enabled else EconetSessionStatus.DISABLED
            self._cookies = []
            self._validated_at = None
            self._expires_at = None
            self._last_error_kind = error_kind
            return self.snapshot()

    def mark_invalid(self, error_kind: str = "session_invalid") -> dict[str, Any]:
        with self._lock:
            self._status = EconetSessionStatus.INVALID if self._enabled else EconetSessionStatus.DISABLED
            self._cookies = []
            self._validated_at = None
            self._expires_at = None
            self._last_error_kind = error_kind
            return self.snapshot()

    def mark_error(self, error_kind: str = "transport_error") -> dict[str, Any]:
        with self._lock:
            self._assert_enabled_locked()
            self._status = EconetSessionStatus.ERROR if self._cookies else EconetSessionStatus.NOT_LOADED
            self._last_error_kind = error_kind
            return self.snapshot()

    def clear(self) -> dict[str, Any]:
        with self._lock:
            self._cookies = []
            self._loaded_at = None
            self._validated_at = None
            self._expires_at = None
            self._last_error_kind = None
            self._status = EconetSessionStatus.DISABLED if not self._enabled else EconetSessionStatus.NOT_LOADED
            self._generation += 1
            return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._refresh_expiration_locked()
            return {
                "status": self._status.value,
                "cookie_count": len(self._cookies),
                "cookie_names": sorted(cookie["name"] for cookie in self._cookies),
                "loaded_at": self._loaded_at.isoformat() if self._loaded_at is not None else None,
                "validated_at": self._validated_at.isoformat() if self._validated_at is not None else None,
                "expires_at": self._expires_at.isoformat() if self._expires_at is not None else None,
                "last_error_kind": self._last_error_kind,
                "generation": self._generation,
            }

    def _normalize_cookie(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip().lower()
        path = str(item.get("path") or "").strip()
        if not name:
            raise EconetSessionInvalidError("Econet session import rejected a cookie without name.")
        if not value:
            raise EconetSessionInvalidError("Econet session import rejected a cookie without value.")
        if len(value.encode("utf-8")) > MAX_COOKIE_BYTES:
            raise EconetSessionInvalidError("Econet session import rejected an oversized cookie.")
        if domain not in ALLOWED_COOKIE_DOMAINS:
            raise EconetSessionInvalidError("Econet session import rejected a cookie from a disallowed domain.")
        if not path.startswith("/"):
            raise EconetSessionInvalidError("Econet session import rejected a cookie with invalid path.")
        if any(name.startswith(prefix) for prefix in ANALYTICS_COOKIE_PREFIXES):
            return None
        if name not in ALLOWED_COOKIE_NAMES:
            raise EconetSessionInvalidError("Econet session import rejected a cookie name outside the allowlist.")
        return {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "expires": item.get("expires"),
            "httpOnly": bool(item.get("httpOnly", False)),
            "secure": bool(item.get("secure", False)),
            "sameSite": str(item.get("sameSite") or "Lax"),
        }

    def _assert_enabled_locked(self) -> None:
        if not self._enabled:
            raise EconetSessionDisabledError("Econet assisted session is disabled.")

    def _assert_loaded_locked(self) -> None:
        self._refresh_expiration_locked()
        if self._status == EconetSessionStatus.EXPIRED:
            raise EconetSessionExpiredError("Econet session has expired.")
        if not self._cookies:
            raise EconetSessionNotLoadedError("Econet session is not loaded.")

    def _refresh_expiration_locked(self) -> None:
        if not self._enabled:
            self._status = EconetSessionStatus.DISABLED
            return
        if not self._cookies and self._status != EconetSessionStatus.INVALID:
            if self._status not in {EconetSessionStatus.ERROR, EconetSessionStatus.EXPIRED}:
                self._status = EconetSessionStatus.NOT_LOADED
            return
        if self._expires_at is not None and self._expires_at <= _utcnow():
            self._cookies = []
            self._validated_at = None
            self._expires_at = None
            self._status = EconetSessionStatus.EXPIRED
            self._last_error_kind = "max_age_exceeded"


_SESSION: EconetAssistedSession | None = None


def get_econet_assisted_session(settings: Settings | None = None) -> EconetAssistedSession:
    global _SESSION
    observed_settings = settings or get_settings()
    if _SESSION is None:
        _SESSION = EconetAssistedSession(
            enabled=observed_settings.econet_assisted_session_enabled,
            max_age_minutes=observed_settings.econet_session_max_age_minutes,
        )
    else:
        _SESSION.configure(
            enabled=observed_settings.econet_assisted_session_enabled,
            max_age_minutes=observed_settings.econet_session_max_age_minutes,
        )
    return _SESSION


def reset_econet_assisted_session() -> None:
    global _SESSION
    _SESSION = None
