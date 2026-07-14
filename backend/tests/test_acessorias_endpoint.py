from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.core.security import get_password_hash
from backend.app.services.auth import ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.app.services.integrations.acessorias.client import AcessoriasConfigurationError
from backend.app.services.integrations.acessorias.sync import AcessoriasSyncResult


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


def _seed_auth_context(db_session, *, role: str, slug: str) -> tuple[User, Organization]:
    organization = Organization(name=f"Org {slug}", slug=slug)
    db_session.add(organization)
    db_session.flush()
    user = User(
        email=f"{slug}@example.local",
        full_name=slug,
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
    db_session.add(
        FiscalPeriod(
            organization_id=organization.id,
            year=2026,
            month=6,
            competencia="2026-06",
            status="OPEN",
        )
    )
    db_session.flush()
    return user, organization


def _login_headers(client: TestClient, *, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "ChangeMe123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/integrations/acessorias/sync", json={"period": "2026-06"})

    assert response.status_code == 401


def test_endpoint_rejects_view_role(client: TestClient, db_session) -> None:
    user, _ = _seed_auth_context(db_session, role=ROLE_VIEW, slug="org-view")
    headers = _login_headers(client, email=user.email)

    response = client.post("/api/v1/integrations/acessorias/sync", json={"period": "2026-06"}, headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_DEV])
def test_endpoint_allows_admin_and_dev_with_controlled_response(client: TestClient, db_session, monkeypatch, role: str) -> None:
    user, organization = _seed_auth_context(db_session, role=role, slug=f"org-{role.lower()}")

    def fake_sync(*args, **kwargs):
        assert kwargs["organization"].id == organization.id
        return AcessoriasSyncResult(run=None, summary={"companies_received": 1}, errors=[], dry_run=True)

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.acessorias.sync_acessorias_period",
        fake_sync,
    )
    headers = _login_headers(client, email=user.email)

    response = client.post(
        "/api/v1/integrations/acessorias/sync",
        json={"period": "2026-06", "dry_run": True},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] is None
    assert "token" not in str(payload).lower()
    assert "payload" not in str(payload).lower()


def test_endpoint_rejects_company_from_other_organization(client: TestClient, db_session) -> None:
    user, organization = _seed_auth_context(db_session, role=ROLE_ADMIN, slug="org-admin")
    other = Organization(name="Other Org", slug="other-org")
    db_session.add(other)
    db_session.flush()
    foreign_company = ExternalCompany(
        organization_id=other.id,
        cnpj="99999999000199",
        razao_social="Outra Empresa",
        active=True,
    )
    db_session.add(foreign_company)
    db_session.flush()
    headers = _login_headers(client, email=user.email)

    response = client.post(
        "/api/v1/integrations/acessorias/sync",
        json={"period": "2026-06", "company_id": foreign_company.id},
        headers=headers,
    )

    assert response.status_code == 400


def test_endpoint_returns_controlled_configuration_error(client: TestClient, db_session, monkeypatch) -> None:
    user, _ = _seed_auth_context(db_session, role=ROLE_ADMIN, slug="org-admin-config")
    headers = _login_headers(client, email=user.email)

    def raise_config(*args, **kwargs):
        raise AcessoriasConfigurationError("ACESSORIAS_API_TOKEN is required for Acessorias sync.")

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.acessorias.sync_acessorias_period",
        raise_config,
    )

    response = client.post("/api/v1/integrations/acessorias/sync", json={"period": "2026-06"}, headers=headers)

    assert response.status_code == 400
