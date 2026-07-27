from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import get_password_hash
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.services.auth import ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.app.services.integrations.econet.assisted_session import reset_econet_assisted_session


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    reset_econet_assisted_session()
    get_settings.cache_clear()
    original_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db_session.commit = original_commit  # type: ignore[method-assign]
        get_settings.cache_clear()


def _seed_user(db_session, *, role: str) -> tuple[User, str]:
    organization = Organization(name=f"Org {role}", slug=f"org-econet-{role.lower()}")
    db_session.add(organization)
    db_session.flush()
    user = User(
        email=f"econet-{role.lower()}@example.local",
        full_name="Tester",
        password_hash=get_password_hash("ChangeMe123!"),
        global_role=role,
        is_active=True,
        token_version=0,
        default_organization_id=organization.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserOrganization(user_id=user.id, organization_id=organization.id, is_active=True))
    db_session.flush()
    return user, "ChangeMe123!"


def _headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _payload(value: str = "sensitive-cookie") -> dict[str, object]:
    return {
        "cookies": [
            {
                "name": "PHPSESSID",
                "value": value,
                "domain": ".econeteditora.com.br",
                "path": "/",
            }
        ]
    }


def test_import_requires_admin_or_dev(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_VIEW)
    response = client.post("/api/v1/integrations/econet/session/import", headers=_headers(client, email=user.email, password=password), json=_payload())
    assert response.status_code == 403


def test_probe_requires_admin_or_dev(client: TestClient, db_session) -> None:
    user, password = _seed_user(db_session, role=ROLE_VIEW)
    response = client.post("/api/v1/integrations/econet/session/probe", headers=_headers(client, email=user.email, password=password))
    assert response.status_code == 403


def test_clear_requires_admin_or_dev(client: TestClient, db_session) -> None:
    user, password = _seed_user(db_session, role=ROLE_VIEW)
    response = client.delete("/api/v1/integrations/econet/session", headers=_headers(client, email=user.email, password=password))
    assert response.status_code == 403


def test_view_can_read_sanitized_status(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_VIEW)
    response = client.get("/api/v1/integrations/econet/session/status", headers=_headers(client, email=user.email, password=password))
    assert response.status_code == 200
    assert "value" not in response.text


def test_disabled_import_returns_controlled_error(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "false")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_ADMIN)
    response = client.post("/api/v1/integrations/econet/session/import", headers=_headers(client, email=user.email, password=password), json=_payload())
    assert response.status_code == 503


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_DEV])
def test_import_returns_loaded_unvalidated(client: TestClient, db_session, monkeypatch, role: str) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=role)
    response = client.post("/api/v1/integrations/econet/session/import", headers=_headers(client, email=user.email, password=password), json=_payload())
    assert response.status_code == 200
    assert response.json()["status"] == "LOADED_UNVALIDATED"


def test_probe_returns_valid_without_html(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_ADMIN)
    headers = _headers(client, email=user.email, password=password)
    client.post("/api/v1/integrations/econet/session/import", headers=headers, json=_payload())
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.EconetClient.probe_session",
        lambda self: {
            "status": "VALID",
            "cookie_count": 1,
            "cookie_names": ["PHPSESSID"],
            "loaded_at": "2026-07-21T00:00:00+00:00",
            "validated_at": "2026-07-21T00:01:00+00:00",
            "expires_at": "2026-07-21T08:01:00+00:00",
            "last_error_kind": None,
            "generation": 1,
        },
    )
    response = client.post("/api/v1/integrations/econet/session/probe", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "VALID"
    assert "<html" not in response.text.lower()


def test_clear_returns_not_loaded(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_ADMIN)
    headers = _headers(client, email=user.email, password=password)
    client.post("/api/v1/integrations/econet/session/import", headers=headers, json=_payload())
    response = client.delete("/api/v1/integrations/econet/session", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_LOADED"


def test_endpoint_response_never_contains_cookie_value(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = _seed_user(db_session, role=ROLE_ADMIN)
    headers = _headers(client, email=user.email, password=password)
    response = client.post("/api/v1/integrations/econet/session/import", headers=headers, json=_payload("top-secret-cookie"))
    assert response.status_code == 200
    assert "top-secret-cookie" not in response.text
