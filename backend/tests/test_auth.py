from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.core.config import REPO_ROOT, Settings, get_settings
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.services.auth import ROLE_ADMIN
from backend.scripts.create_initial_admin import create_initial_admin


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


def seed_user(
    db_session,
    *,
    email: str = "admin@example.local",
    password: str = "StrongPass123",
    role: str = ROLE_ADMIN,
    is_active: bool = True,
) -> tuple[User, Organization, str]:
    organization = Organization(name="Lumen Org", slug=f"lumen-org-{email.split('@')[0]}")
    db_session.add(organization)
    db_session.flush()

    user = User(
        email=email,
        full_name="Admin User",
        password_hash=get_password_hash(password),
        global_role=role,
        is_active=is_active,
        default_organization_id=organization.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserOrganization(user_id=user.id, organization_id=organization.id, is_active=True))
    db_session.flush()
    return user, organization, password


def login(client: TestClient, *, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def isolated_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_auth_migrations_tables_exist(db_session) -> None:
    inspector = inspect(db_session.bind)

    assert "organizations" in inspector.get_table_names()
    assert "users" in inspector.get_table_names()
    assert "user_organizations" in inspector.get_table_names()


def test_login_valid_returns_access_and_refresh(client: TestClient, db_session) -> None:
    user, _, password = seed_user(db_session)

    response = login(client, email=user.email, password=password)

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 900
    assert payload["access_token"]
    assert payload["refresh_token"]


def test_login_invalid_returns_401(client: TestClient, db_session) -> None:
    user, _, _ = seed_user(db_session)

    response = login(client, email=user.email, password="wrong-password")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials."


def test_login_inactive_user_returns_403(client: TestClient, db_session) -> None:
    user, _, password = seed_user(db_session, is_active=False)

    response = login(client, email=user.email, password=password)

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user."


def test_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_with_valid_token_returns_user_and_org(client: TestClient, db_session) -> None:
    user, organization, password = seed_user(db_session)
    token_response = login(client, email=user.email, password=password).json()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_response['access_token']}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == user.email
    assert payload["global_role"] == ROLE_ADMIN
    assert payload["organization"]["id"] == organization.id
    assert payload["organization"]["slug"] == organization.slug


def test_refresh_valid_generates_new_access_token(client: TestClient, db_session) -> None:
    user, _, password = seed_user(db_session)
    token_response = login(client, email=user.email, password=password).json()

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token_response["refresh_token"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"] is None
    assert payload["expires_in"] == 900


def test_refresh_invalid_fails(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid-token"})

    assert response.status_code == 401


def test_logout_invalidates_old_token_via_token_version(client: TestClient, db_session) -> None:
    user, _, password = seed_user(db_session)
    token_response = login(client, email=user.email, password=password).json()
    access_token = token_response["access_token"]

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": token_response["refresh_token"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 200

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_response.status_code == 401


def test_token_with_org_without_active_link_is_rejected(client: TestClient, db_session) -> None:
    user, _, _ = seed_user(db_session)
    other_org = Organization(name="Other Org", slug="other-org")
    db_session.add(other_org)
    db_session.flush()

    token = create_access_token(
        subject=str(user.id),
        org_id=other_org.id,
        role=user.global_role,
        token_version=user.token_version,
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"] == "User has no active organization link."


def test_seed_admin_is_idempotent(db_session, monkeypatch) -> None:
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "seed-admin@example.local")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "SeedPass123")
    monkeypatch.setenv("INITIAL_ADMIN_FULL_NAME", "Seed Admin")
    monkeypatch.setenv("INITIAL_ORG_NAME", "Seed Org")
    monkeypatch.setenv("INITIAL_ORG_SLUG", "seed-org")

    settings = isolated_settings()
    create_initial_admin(db_session, settings)
    create_initial_admin(db_session, settings)

    users = db_session.scalars(select(User).where(User.email == "seed-admin@example.local")).all()
    orgs = db_session.scalars(select(Organization).where(Organization.slug == "seed-org")).all()
    memberships = db_session.scalars(select(UserOrganization)).all()

    assert len(users) == 1
    assert len(orgs) == 1
    assert len(memberships) == 1
    assert users[0].default_organization_id == orgs[0].id


def test_seed_admin_requires_password(db_session, monkeypatch) -> None:
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "seed-admin@example.local")
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("INITIAL_ORG_NAME", "Seed Org")
    monkeypatch.setenv("INITIAL_ORG_SLUG", "seed-org")

    settings = isolated_settings()

    with pytest.raises(SystemExit, match="INITIAL_ADMIN_PASSWORD is required"):
        create_initial_admin(db_session, settings)


def test_seed_admin_proceeds_with_explicit_password_when_env_file_is_disabled(db_session, monkeypatch) -> None:
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "seed-admin@example.local")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "SeedPass123")
    monkeypatch.setenv("INITIAL_ADMIN_FULL_NAME", "Seed Admin")
    monkeypatch.setenv("INITIAL_ORG_NAME", "Seed Org")
    monkeypatch.setenv("INITIAL_ORG_SLUG", "seed-org")

    settings = isolated_settings()

    create_initial_admin(db_session, settings)

    user = db_session.scalar(select(User).where(User.email == "seed-admin@example.local"))
    organization = db_session.scalar(select(Organization).where(Organization.slug == "seed-org"))

    assert user is not None
    assert organization is not None
    assert user.default_organization_id == organization.id


def test_settings_default_env_file_configuration_is_preserved() -> None:
    assert Settings.model_config.get("env_file") == REPO_ROOT / ".env"


def test_get_settings_can_disable_dotenv(monkeypatch) -> None:
    monkeypatch.setenv("LUMEN_DISABLE_DOTENV", "1")
    monkeypatch.delenv("ACESSORIAS_API_TOKEN", raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()

    assert settings.acessorias_api_token is None
