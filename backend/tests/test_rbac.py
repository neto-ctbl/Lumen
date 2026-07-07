from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.api.deps import get_current_auth_context, require_roles
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.services.auth import AuthContext, ROLE_ADMIN, ROLE_VIEW


def _build_context(role: str) -> AuthContext:
    organization = Organization(id=1, name="Lumen", slug="lumen", is_active=True)
    user = User(
        id=1,
        email="rbac@example.local",
        password_hash="hash",
        global_role=role,
        is_active=True,
        token_version=0,
        default_organization_id=1,
    )
    return AuthContext(user=user, organization=organization, claims={})


def _build_test_app(role: str) -> TestClient:
    test_app = FastAPI()

    @test_app.post("/admin-action")
    def admin_action(_: User = Depends(require_roles(ROLE_ADMIN))) -> dict[str, str]:
        return {"status": "ok"}

    test_app.dependency_overrides[get_current_auth_context] = lambda: _build_context(role)
    return TestClient(test_app)


def test_require_roles_allows_admin() -> None:
    client = _build_test_app(ROLE_ADMIN)

    response = client.post("/admin-action")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_require_roles_blocks_view_for_admin_mutation() -> None:
    client = _build_test_app(ROLE_VIEW)

    response = client.post("/admin-action")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions."
