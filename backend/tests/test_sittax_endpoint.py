from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.services.auth import ROLE_ADMIN, ROLE_DEV, ROLE_VIEW


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
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


def _seed_user(db_session, *, role: str) -> tuple[User, str]:
    organization = Organization(name=f"Org {role}", slug=f"org-{role.lower()}")
    db_session.add(organization)
    db_session.flush()
    user = User(
        email=f"{role.lower()}@example.local",
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


def test_sittax_sync_endpoint_requires_admin_or_dev(client: TestClient, db_session) -> None:
    user, password = _seed_user(db_session, role=ROLE_VIEW)

    response = client.post(
        "/api/v1/integrations/sittax/sync",
        headers=_headers(client, email=user.email, password=password),
        json={"period": "2026-06", "dry_run": True},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_DEV])
def test_sittax_sync_endpoint_reuses_service(client: TestClient, db_session, monkeypatch, role: str) -> None:
    user, password = _seed_user(db_session, role=role)

    class _Run:
        id = 99

    class _Result:
        run = _Run()
        status = "DRY_RUN"
        dry_run = True
        summary = {"companies_processed": 0}
        errors: list[dict] = []

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.sittax.sync_sittax_operational",
        lambda *args, **kwargs: _Result(),
    )

    response = client.post(
        "/api/v1/integrations/sittax/sync",
        headers=_headers(client, email=user.email, password=password),
        json={"period": "2026-06", "dry_run": True, "scope": "TASKS"},
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == 99
    assert response.json()["status"] == "DRY_RUN"
