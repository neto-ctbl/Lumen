from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.integrations.econet.assisted_session import EconetAssistedSession
from backend.app.services.integrations.econet.errors import (
    EconetSessionDisabledError,
    EconetSessionExpiredError,
    EconetSessionInvalidError,
)


def build_payload(*, value: str = "secret-cookie") -> dict[str, object]:
    return {
        "cookies": [
            {
                "name": "PHPSESSID",
                "value": value,
                "domain": ".econeteditora.com.br",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax",
            }
        ]
    }


def build_session(*, enabled: bool = True, max_age_minutes: int = 480) -> EconetAssistedSession:
    return EconetAssistedSession(enabled=enabled, max_age_minutes=max_age_minutes)


def test_session_starts_disabled() -> None:
    session = build_session(enabled=False)
    assert session.snapshot()["status"] == "DISABLED"


def test_session_starts_not_loaded_when_enabled() -> None:
    session = build_session()
    assert session.snapshot()["status"] == "NOT_LOADED"


def test_imports_allowed_cookies() -> None:
    session = build_session()
    snapshot = session.import_storage_state(build_payload())
    assert snapshot["status"] == "LOADED_UNVALIDATED"
    assert snapshot["cookie_names"] == ["PHPSESSID"]


def test_rejects_disallowed_domain() -> None:
    session = build_session()
    payload = build_payload()
    payload["cookies"][0]["domain"] = ".google.com"  # type: ignore[index]
    with pytest.raises(EconetSessionInvalidError):
        session.import_storage_state(payload)


def test_rejects_empty_cookie_list() -> None:
    session = build_session()
    with pytest.raises(EconetSessionInvalidError):
        session.import_storage_state({"cookies": []})


def test_rejects_analytics_only() -> None:
    session = build_session()
    with pytest.raises(EconetSessionInvalidError):
        session.import_storage_state(
            {
                "cookies": [
                    {"name": "_ga", "value": "x", "domain": ".econeteditora.com.br", "path": "/"},
                ]
            }
        )


def test_ignores_or_rejects_local_storage() -> None:
    session = build_session()
    with pytest.raises(EconetSessionInvalidError):
        session.import_storage_state({"cookies": build_payload()["cookies"], "origins": []})


def test_rejects_duplicate_conflicting_cookie() -> None:
    session = build_session()
    payload = build_payload()
    payload["cookies"].append(  # type: ignore[union-attr]
        {
            "name": "PHPSESSID",
            "value": "other",
            "domain": ".econeteditora.com.br",
            "path": "/",
        }
    )
    with pytest.raises(EconetSessionInvalidError):
        session.import_storage_state(payload)


def test_snapshot_never_contains_values() -> None:
    session = build_session()
    snapshot = session.import_storage_state(build_payload(value="very-secret"))
    assert "very-secret" not in repr(snapshot)
    assert "very-secret" not in repr(session)


def test_clear_session_is_idempotent() -> None:
    session = build_session()
    session.import_storage_state(build_payload())
    assert session.clear()["status"] == "NOT_LOADED"
    assert session.clear()["status"] == "NOT_LOADED"


def test_session_expires_by_max_age() -> None:
    session = build_session(max_age_minutes=1)
    session.import_storage_state(build_payload())
    session._expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # type: ignore[attr-defined]
    with pytest.raises(EconetSessionExpiredError):
        session.build_cookie_jar()
    assert session.snapshot()["status"] == "EXPIRED"


def test_session_generation_changes_on_import() -> None:
    session = build_session()
    first = session.import_storage_state(build_payload())
    second = session.import_storage_state(build_payload(value="second"))
    assert second["generation"] > first["generation"]


def test_concurrent_import_and_clear_are_safe() -> None:
    session = build_session()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(session.import_storage_state, build_payload()),
            executor.submit(session.clear),
        ]
        for future in futures:
            future.result(timeout=1)
    assert session.snapshot()["status"] in {"NOT_LOADED", "LOADED_UNVALIDATED"}


def test_disabled_session_rejects_import() -> None:
    session = build_session(enabled=False)
    with pytest.raises(EconetSessionDisabledError):
        session.import_storage_state(build_payload())
