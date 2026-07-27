from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.services.integrations.econet.assisted_session import get_econet_assisted_session, reset_econet_assisted_session


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


def seed_auth_context(db_session, *, slug: str) -> tuple[User, str]:
    organization = Organization(name=f"Org {slug}", slug=slug)
    db_session.add(organization)
    db_session.flush()
    user = User(
        email=f"{slug}@example.local",
        full_name="Reader User",
        password_hash=get_password_hash("ChangeMe123!"),
        global_role="VIEW",
        is_active=True,
        token_version=0,
        default_organization_id=organization.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserOrganization(user_id=user.id, organization_id=organization.id, is_active=True))
    db_session.flush()
    return user, "ChangeMe123!"


def login_headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _econet_item(payload: dict[str, object]) -> dict[str, object]:
    return next(item for item in payload["items"] if item["provider"] == "ECONET")


def test_econet_health_disabled(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "false")
    get_settings.cache_clear()
    user, password = seed_auth_context(db_session, slug="econet-health-disabled")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert response.status_code == 200
    assert _econet_item(response.json())["session_status"] == "DISABLED"


def test_econet_health_waiting_manual_login(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = seed_auth_context(db_session, slug="econet-health-not-loaded")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert _econet_item(response.json())["session_status"] == "NOT_LOADED"


def test_econet_health_loaded_unvalidated(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    session = get_econet_assisted_session()
    session.import_storage_state({"cookies": [{"name": "PHPSESSID", "value": "x", "domain": ".econeteditora.com.br", "path": "/"}]})
    user, password = seed_auth_context(db_session, slug="econet-health-loaded")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert _econet_item(response.json())["session_status"] == "LOADED_UNVALIDATED"


def test_econet_health_valid(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    session = get_econet_assisted_session()
    session.import_storage_state({"cookies": [{"name": "PHPSESSID", "value": "x", "domain": ".econeteditora.com.br", "path": "/"}]})
    session.mark_valid()
    user, password = seed_auth_context(db_session, slug="econet-health-valid")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert _econet_item(response.json())["session_status"] == "VALID"


def test_econet_health_expired(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    session = get_econet_assisted_session()
    session.import_storage_state({"cookies": [{"name": "PHPSESSID", "value": "x", "domain": ".econeteditora.com.br", "path": "/"}]})
    session.mark_expired()
    user, password = seed_auth_context(db_session, slug="econet-health-expired")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert _econet_item(response.json())["session_status"] == "EXPIRED"


def test_econet_health_includes_cache_counts(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae="6201501",
            cnae_formatted="6201-5/01",
            description="Desc",
            econet_id_cnae="123",
            activity_types=[],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="III",
            simples_annex_conditional=None,
            factor_r_applicable=None,
            factor_r_threshold=None,
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="UNKNOWN",
            actual_profit_mandatory=None,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version="1",
            content_hash="a" * 64,
            retrieved_at=now,
            expires_at=now - timedelta(days=1),
        )
    )
    db_session.flush()
    user, password = seed_auth_context(db_session, slug="econet-health-cache")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    item = _econet_item(response.json())
    assert item["cache_items"] == 1
    assert item["cache_expired_items"] == 1


def test_econet_health_does_not_call_external_network(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = seed_auth_context(db_session, slug="econet-health-no-network")
    monkeypatch.setattr(
        "backend.app.services.integrations.econet.client.EconetClient.probe_session",
        lambda self: (_ for _ in ()).throw(AssertionError("health must not call Econet probe")),
    )
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert response.status_code == 200


def test_econet_health_survives_empty_cache(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    get_settings.cache_clear()
    user, password = seed_auth_context(db_session, slug="econet-health-empty-cache")
    response = client.get("/api/v1/lumen/integrations/health", headers=login_headers(client, email=user.email, password=password))
    assert _econet_item(response.json())["cache_items"] == 0
