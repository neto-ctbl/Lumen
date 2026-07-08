from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.audit_log import AuditLog
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.core.config import get_settings


@pytest.fixture()
def client(db_session, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ECONTROLE_WEBHOOK_TOKEN", "secret-webhook-token")
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


def _create_org(db_session, slug: str = "org-webhook") -> Organization:
    organization = Organization(name="Org Webhook", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _headers(token: str | None = "secret-webhook-token") -> dict[str, str]:
    if token is None:
        return {}
    return {"X-Lumen-Webhook-Token": token}


def _upsert_payload(org_slug: str = "org-webhook") -> dict[str, object]:
    return {
        "org_slug": org_slug,
        "id": "123",
        "profile_id": "456",
        "cnpj": "19.163.109/0001-78",
        "razao_social": "AC SOARES LTDA",
        "nome_fantasia": "AC Soares",
        "updated_at": "2026-07-07T10:00:00-03:00",
    }


def test_webhook_without_token_returns_401(client: TestClient, db_session) -> None:
    _create_org(db_session)

    response = client.post("/api/v1/webhooks/econtrole/company-upsert", json=_upsert_payload(), headers=_headers(None))

    assert response.status_code == 401


def test_webhook_with_invalid_token_returns_401(client: TestClient, db_session) -> None:
    _create_org(db_session)

    response = client.post("/api/v1/webhooks/econtrole/company-upsert", json=_upsert_payload(), headers=_headers("wrong"))

    assert response.status_code == 401


def test_upsert_webhook_with_valid_token_creates_company(client: TestClient, db_session) -> None:
    _create_org(db_session)

    response = client.post("/api/v1/webhooks/econtrole/company-upsert", json=_upsert_payload(), headers=_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["created"] is True
    company = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == payload["company_id"]))
    assert company is not None
    assert company.cnpj == "19163109000178"
    audit = db_session.scalar(select(AuditLog).where(AuditLog.resource_id == str(company.id)))
    assert audit is not None
    assert audit.event_type == "webhook.econtrole.company_upsert"


def test_delete_webhook_with_valid_token_soft_deletes_company(client: TestClient, db_session) -> None:
    _create_org(db_session)
    create_response = client.post("/api/v1/webhooks/econtrole/company-upsert", json=_upsert_payload(), headers=_headers())
    company_id = create_response.json()["company_id"]

    response = client.post(
        "/api/v1/webhooks/econtrole/company-delete",
        json={"org_slug": "org-webhook", "cnpj": "19.163.109/0001-78"},
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == company_id
    assert payload["deleted"] is True
    company = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == company_id))
    assert company is not None
    assert company.active is False
    assert company.sync_status == "DELETED_ECONTROLE"


def test_upsert_webhook_invalid_payload_returns_422(client: TestClient, db_session) -> None:
    _create_org(db_session)

    response = client.post(
        "/api/v1/webhooks/econtrole/company-upsert",
        json={"org_slug": "org-webhook", "cnpj": "19.163.109/0001-78"},
        headers=_headers(),
    )

    assert response.status_code == 422
