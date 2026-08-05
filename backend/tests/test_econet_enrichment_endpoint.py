from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.services.factor_r import FactorRPotentialResult
from backend.app.services.integrations.econet.enrichment import EnrichmentItemResult
from datetime import datetime, timedelta, timezone


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


def _seed_context(db_session, *, role: str) -> tuple[User, str, Organization]:
    organization = Organization(name=f"Org {role}", slug=f"org-enrich-{role.lower()}")
    db_session.add(organization)
    db_session.flush()
    password = "ChangeMe123!"
    user = User(
        email=f"{role.lower()}@example.local",
        full_name=role,
        password_hash=get_password_hash(password),
        global_role=role,
        is_active=True,
        token_version=0,
        default_organization_id=organization.id,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserOrganization(user_id=user.id, organization_id=organization.id, is_active=True))
    company = ExternalCompany(organization_id=organization.id, cnpj="19163109000178", razao_social="Empresa", active=True)
    db_session.add(company)
    db_session.flush()
    db_session.add(
        CompanyCnae(
            company_id=company.id,
            cnae="8630503",
            cnae_formatted="8630-5/03",
            is_primary=True,
            source="ECONTROLE",
            active=True,
            first_seen_at=company.created_at,
            last_seen_at=company.created_at,
        )
    )
    db_session.flush()
    return user, password, organization


def _headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_enrich_requires_admin_or_dev(client: TestClient, db_session, monkeypatch) -> None:
    user, password, _ = _seed_context(db_session, role="VIEW")
    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.enrich_cnaes",
        lambda *args, **kwargs: None,
    )
    response = client.post("/api/v1/integrations/econet/enrich", headers=_headers(client, email=user.email, password=password), json={})
    assert response.status_code == 403


def test_cache_only_works_without_session(client: TestClient, db_session, monkeypatch) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")

    class Result:
        status = "SUCCESS"
        dry_run = True
        summary = {"processed": 1}
        items = []
        catalog_summary = {}

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.enrich_cnaes",
        lambda *args, **kwargs: Result(),
    )
    response = client.post(
        "/api/v1/integrations/econet/enrich",
        headers=_headers(client, email=user.email, password=password),
        json={"cache_only": True, "dry_run": True},
    )
    assert response.status_code == 200
    assert "cookie" not in response.text.lower()
    assert "html" not in response.text.lower()


def test_enrichment_accepts_limit_50(client: TestClient, db_session, monkeypatch) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")

    class Result:
        status = "SUCCESS"
        dry_run = True
        summary = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
        items = []
        catalog_summary = {}

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.enrich_cnaes",
        lambda *args, **kwargs: Result(),
    )
    response = client.post(
        "/api/v1/integrations/econet/enrich",
        headers=_headers(client, email=user.email, password=password),
        json={"limit": 50, "dry_run": True, "cache_only": True},
    )
    assert response.status_code == 200


def test_enrichment_rejects_limit_51(client: TestClient, db_session) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")
    response = client.post(
        "/api/v1/integrations/econet/enrich",
        headers=_headers(client, email=user.email, password=password),
        json={"limit": 51, "dry_run": True, "cache_only": True},
    )
    assert response.status_code == 422


def test_enrich_serializes_items_with_slots_dataclass(client: TestClient, db_session, monkeypatch) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")

    class Result:
        status = "SUCCESS"
        dry_run = True
        summary = {"processed": 1, "created": 1, "updated": 0, "errors": 0}
        items = [
            EnrichmentItemResult(
                cnae="7020400",
                status="CREATED",
                cache_record_id=123,
                parse_status="PARSED",
                message=None,
            )
        ]
        catalog_summary = {}

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.enrich_cnaes",
        lambda *args, **kwargs: Result(),
    )
    response = client.post(
        "/api/v1/integrations/econet/enrich",
        headers=_headers(client, email=user.email, password=password),
        json={"dry_run": True, "cache_only": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == [
        {
            "cnae": "7020400",
            "status": "CREATED",
            "cache_record_id": 123,
            "parse_status": "PARSED",
            "message": None,
        }
    ]


def test_enrich_serializes_factor_r_results(client: TestClient, db_session, monkeypatch) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")

    class Result:
        status = "SUCCESS"
        dry_run = False
        summary = {"processed": 1, "created": 1, "updated": 0, "errors": 0}
        items = []
        catalog_summary = {}
        factor_r_results = [
            FactorRPotentialResult(
                company_id=78,
                status="APPLICABLE",
                factor_r_potential=True,
                cnaes_total=1,
                cnaes_with_cache=1,
                positive_cnaes=["7020400"],
                negative_cnaes=[],
                missing_cnaes=[],
                annex_default="V",
                annex_conditional="III",
                factor_r_threshold="28.00",
            )
        ]

    monkeypatch.setattr(
        "backend.app.api.v1.endpoints.integrations.econet.enrich_cnaes",
        lambda *args, **kwargs: Result(),
    )
    response = client.post(
        "/api/v1/integrations/econet/enrich",
        headers=_headers(client, email=user.email, password=password),
        json={"company_ids": [78], "dry_run": False, "cache_only": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["factor_r_results"] == [
        {
            "company_id": 78,
            "status": "APPLICABLE",
            "factor_r_potential": True,
            "cnaes_total": 1,
            "cnaes_with_cache": 1,
            "positive_cnaes": ["7020400"],
            "negative_cnaes": [],
            "missing_cnaes": [],
            "annex_default": "V",
            "annex_conditional": "III",
            "factor_r_threshold": "28.00",
        }
    ]


def test_get_factor_r_potential_returns_200(client: TestClient, db_session) -> None:
    user, password, _ = _seed_context(db_session, role="ADMIN")
    company = db_session.query(ExternalCompany).filter_by(cnpj="19163109000178").one()
    now = datetime.now(timezone.utc)
    db_session.add(
        EconetCnaeCache(
            cnae="8630503",
            cnae_formatted="8630-5/03",
            description="servicos medicos",
            econet_id_cnae="999",
            activity_types=[],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="V",
            simples_annex_conditional="III",
            factor_r_applicable=True,
            factor_r_threshold="28.00",
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
            parser_version="econet-html-v2",
            content_hash="a" * 64,
            retrieved_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    db_session.flush()
    response = client.get(
        f"/api/v1/lumen/companies/{company.id}/factor-r-potential",
        headers=_headers(client, email=user.email, password=password),
    )
    assert response.status_code == 200
    assert response.json()["factor_r_potential"] is True
