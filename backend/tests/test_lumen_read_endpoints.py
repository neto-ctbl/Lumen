from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.models.user_organization import UserOrganization
from backend.app.core.security import get_password_hash
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


def seed_auth_context(db_session, *, role: str = ROLE_VIEW, slug: str = "org-main") -> tuple[User, Organization, str]:
    organization = Organization(name=f"Org {slug}", slug=slug)
    db_session.add(organization)
    db_session.flush()

    user = User(
        email=f"{slug}@example.local",
        full_name="Reader User",
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
    return user, organization, "ChangeMe123!"


def login_headers(client: TestClient, *, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def seed_company(
    db_session,
    *,
    organization_id: int,
    cnpj: str,
    razao_social: str,
    active: bool = True,
    inscricao_estadual: str | None = None,
) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization_id,
        cnpj=cnpj,
        razao_social=razao_social,
        nome_fantasia=razao_social.split()[0],
        apelido_pasta=razao_social.split()[0],
        inscricao_estadual=inscricao_estadual,
        municipio="Goiania",
        uf="GO",
        active=active,
        sync_status="SYNCED",
    )
    db_session.add(company)
    db_session.flush()
    return company


def seed_period(db_session, *, organization_id: int, competencia: str) -> FiscalPeriod:
    year = int(competencia[:4])
    month = int(competencia[5:7])
    period = FiscalPeriod(
        organization_id=organization_id,
        year=year,
        month=month,
        competencia=competencia,
        status="OPEN",
    )
    db_session.add(period)
    db_session.flush()
    return period


def seed_obligation(db_session, *, code: str = "SPED-FISCAL", department: str = "FISCAL") -> FiscalObligation:
    obligation = FiscalObligation(
        code=code,
        name="SPED Fiscal",
        category="ESTADUAL",
        department_default=department,
        source_priority=[],
        active=True,
    )
    db_session.add(obligation)
    db_session.flush()
    return obligation


def seed_run(
    db_session,
    *,
    organization_id: int,
    provider: str = "SITTAX",
    job_name: str = "sync_sittax_operational",
    status: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IntegrationSyncRun:
    run = IntegrationSyncRun(
        organization_id=organization_id,
        integration_account_id=None,
        provider=provider,
        job_name=job_name,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        processed_count=1,
        created_count=0,
        updated_count=0,
        error_count=0 if status == "SUCCESS" else 1,
        summary={},
        run_metadata={},
    )
    db_session.add(run)
    db_session.flush()
    return run


def test_lumen_endpoints_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/lumen/companies")

    assert response.status_code == 401


@pytest.mark.parametrize("role", [ROLE_VIEW, ROLE_ADMIN, ROLE_DEV])
def test_lumen_endpoints_allow_read_roles(client: TestClient, db_session, role: str) -> None:
    user, organization, password = seed_auth_context(db_session, role=role, slug=f"org-{role.lower()}")
    seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    headers = login_headers(client, email=user.email, password=password)

    response = client.get("/api/v1/lumen/companies", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_companies_return_only_active_from_current_organization(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW)
    other_user, other_org, _ = seed_auth_context(db_session, role=ROLE_VIEW, slug="org-other")
    _ = other_user
    seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Ativa 1")
    seed_company(db_session, organization_id=organization.id, cnpj="22222222000122", razao_social="Inativa", active=False)
    seed_company(db_session, organization_id=other_org.id, cnpj="33333333000133", razao_social="Outra Org")
    headers = login_headers(client, email=user.email, password=password)

    response = client.get("/api/v1/lumen/companies", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert [item["razao_social"] for item in payload["items"]] == ["Ativa 1"]


def test_company_summary_handles_null_ie_as_display_only(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session)
    company = seed_company(
        db_session,
        organization_id=organization.id,
        cnpj="11111111000111",
        razao_social="Sem IE Ltda",
        inscricao_estadual=None,
    )
    seed_period(db_session, organization_id=organization.id, competencia="2026-06")
    headers = login_headers(client, email=user.email, password=password)

    response = client.get(f"/api/v1/lumen/companies/{company.id}/summary?period=2026-06", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["inscricao_estadual_display"] == "ISENTO"
    company_db = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == company.id))
    assert company_db is not None
    assert company_db.inscricao_estadual is None


def test_periods_return_sorted_for_current_organization(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session)
    other_user, other_org, _ = seed_auth_context(db_session, slug="org-periods-other")
    _ = other_user
    seed_period(db_session, organization_id=organization.id, competencia="2026-05")
    seed_period(db_session, organization_id=organization.id, competencia="2026-06")
    seed_period(db_session, organization_id=other_org.id, competencia="2027-01")
    headers = login_headers(client, email=user.email, password=password)

    response = client.get("/api/v1/lumen/periods", headers=headers)

    assert response.status_code == 200
    assert [item["competencia"] for item in response.json()["items"]] == ["2026-06", "2026-05"]


def test_dashboard_and_deliveries_return_empty_when_no_statuses_exist(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session)
    seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    seed_period(db_session, organization_id=organization.id, competencia="2026-06")
    headers = login_headers(client, email=user.email, password=password)

    dashboard = client.get("/api/v1/lumen/dashboard?period=2026-06", headers=headers)
    deliveries = client.get("/api/v1/lumen/deliveries?period=2026-06", headers=headers)
    cockpit = client.get("/api/v1/lumen/cockpit?period=2026-06", headers=headers)

    assert dashboard.status_code == 200
    assert dashboard.json()["kpis"]["obligations_total"] == 0
    assert dashboard.json()["kpis"]["delivered_total"] == 0
    assert deliveries.status_code == 200
    assert deliveries.json()["items"] == []
    assert cockpit.status_code == 200
    assert cockpit.json()["items"][0]["overall_status"] == "SEM_DADOS"


def test_dashboard_is_isolated_by_organization(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session)
    _, other_org, _ = seed_auth_context(db_session, slug="org-isolation-other")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    other_company = seed_company(db_session, organization_id=other_org.id, cnpj="22222222000122", razao_social="Beta Ltda")
    period = seed_period(db_session, organization_id=organization.id, competencia="2026-06")
    other_period = seed_period(db_session, organization_id=other_org.id, competencia="2026-06")
    obligation = seed_obligation(db_session)
    other_obligation = seed_obligation(db_session, code="DCTFWEB")
    db_session.add(
        FiscalObligationStatus(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            obligation_id=obligation.id,
            status="PENDENTE",
            responsible_department="FISCAL",
            last_source="MANUAL",
        )
    )
    db_session.add(
        FiscalObligationStatus(
            organization_id=other_org.id,
            company_id=other_company.id,
            period_id=other_period.id,
            obligation_id=other_obligation.id,
            status="ENTREGUE",
            responsible_department="FISCAL",
            last_source="MANUAL",
        )
    )
    db_session.flush()
    headers = login_headers(client, email=user.email, password=password)

    response = client.get("/api/v1/lumen/dashboard?period=2026-06", headers=headers)

    assert response.status_code == 200
    assert response.json()["kpis"]["obligations_total"] == 1
    assert response.json()["kpis"]["delivered_total"] == 0


def test_integrations_health_uses_last_terminal_run_and_flags_stale_running(client: TestClient, db_session, monkeypatch) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="org-health")
    now = datetime.now(timezone.utc)
    seed_run(
        db_session,
        organization_id=organization.id,
        status="SUCCESS",
        started_at=now - timedelta(minutes=30),
        finished_at=now - timedelta(minutes=29),
    )
    seed_run(
        db_session,
        organization_id=organization.id,
        status="RUNNING",
        started_at=now - timedelta(minutes=20),
        finished_at=None,
    )
    headers = login_headers(client, email=user.email, password=password)

    def _boom(*args, **kwargs):
        raise AssertionError("health must not instantiate Sittax session")

    monkeypatch.setattr("backend.app.services.integrations.sittax.session.SittaxSession.from_settings", _boom)
    response = client.get("/api/v1/lumen/integrations/health", headers=headers)

    assert response.status_code == 200
    sittax = next(item for item in response.json()["items"] if item["provider"] == "SITTAX")
    assert sittax["status"] == "SUCCESS"
    assert sittax["last_run_status"] == "SUCCESS"
    assert sittax["active_run_status"] == "RUNNING"
    assert sittax["stale_warning"] is not None


def test_integrations_health_without_runs_returns_nao_iniciada(client: TestClient, db_session) -> None:
    user, _, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="org-health-empty")
    headers = login_headers(client, email=user.email, password=password)

    response = client.get("/api/v1/lumen/integrations/health", headers=headers)

    assert response.status_code == 200
    sittax = next(item for item in response.json()["items"] if item["provider"] == "SITTAX")
    assert sittax["last_run_status"] is None
    assert sittax["active_run_status"] is None
    assert sittax["stale_warning"] is None
