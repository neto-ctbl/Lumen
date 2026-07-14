from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.acessorias_delivery_snapshot import AcessoriasDeliverySnapshot
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.external_company import ExternalCompany
from backend.app.services.integrations.acessorias.sync import FixtureAcessoriasClient, sync_acessorias_period


FIXTURES_DIR = Path("backend/tests/fixtures/acessorias")


def _seed_org_company_period(db_session) -> tuple[Organization, ExternalCompany, FiscalPeriod]:
    organization = Organization(name="Org Acessorias", slug="org-acessorias")
    db_session.add(organization)
    db_session.flush()

    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="11111111000111",
        razao_social="Alpha Ltda",
        nome_fantasia="Alpha",
        active=True,
        raw_econtrole={"regime": "Lucro Real"},
    )
    db_session.add(company)
    db_session.flush()

    period = FiscalPeriod(
        organization_id=organization.id,
        year=2026,
        month=6,
        competencia="2026-06",
        status="OPEN",
    )
    db_session.add(period)
    db_session.flush()

    db_session.add_all(
        [
            FiscalObligation(code="DAS", name="DAS", category="SIMPLES", department_default="FISCAL", source_priority=[]),
            FiscalObligation(code="DEFIS", name="DEFIS", category="SIMPLES", department_default="FISCAL", source_priority=[]),
        ]
    )
    db_session.flush()
    return organization, company, period


def _fixture_client() -> FixtureAcessoriasClient:
    return FixtureAcessoriasClient.from_files(
        companies_path=FIXTURES_DIR / "companies_sample.json",
        deliveries_path=FIXTURES_DIR / "deliveries_sample.json",
    )


def test_sync_acessorias_period_creates_snapshots_and_statuses_idempotently(db_session) -> None:
    organization, company, period = _seed_org_company_period(db_session)

    first = sync_acessorias_period(
        db_session,
        period=period.competencia,
        organization=organization,
        client=_fixture_client(),
    )
    second = sync_acessorias_period(
        db_session,
        period=period.competencia,
        organization=organization,
        client=_fixture_client(),
    )

    company_snapshots = db_session.scalars(select(AcessoriasCompanySnapshot)).all()
    delivery_snapshots = db_session.scalars(select(AcessoriasDeliverySnapshot)).all()
    statuses = db_session.scalars(select(FiscalObligationStatus)).all()
    runs = db_session.scalars(select(IntegrationSyncRun).where(IntegrationSyncRun.provider == "ACESSORIAS")).all()

    assert first.run is not None
    assert second.run is not None
    assert len(company_snapshots) == 2
    assert len(delivery_snapshots) == 3
    assert len(statuses) == 1
    assert len(runs) == 2
    assert statuses[0].company_id == company.id
    assert statuses[0].period_id == period.id
    assert statuses[0].status == "CONFIRMADO_API"


def test_sync_preserves_unmatched_company_and_unmapped_obligation_without_status(db_session) -> None:
    organization, _, period = _seed_org_company_period(db_session)

    result = sync_acessorias_period(
        db_session,
        period=period.competencia,
        organization=organization,
        client=_fixture_client(),
    )

    unmatched = db_session.scalar(
        select(AcessoriasCompanySnapshot).where(AcessoriasCompanySnapshot.external_company_id == "9002")
    )
    unmapped_delivery = db_session.scalar(
        select(AcessoriasDeliverySnapshot).where(AcessoriasDeliverySnapshot.external_delivery_id == "5002")
    )

    assert unmatched is not None
    assert unmatched.company_id is None
    assert unmapped_delivery is not None
    assert unmapped_delivery.obligation_mapping_status == "UNMAPPED"
    assert result.summary["unmapped_obligations"] >= 1


def test_sync_skips_tasks_for_fiscal_statuses(db_session) -> None:
    organization, _, period = _seed_org_company_period(db_session)

    result = sync_acessorias_period(
        db_session,
        period=period.competencia,
        organization=organization,
        client=_fixture_client(),
    )

    task_snapshot = db_session.scalar(
        select(AcessoriasDeliverySnapshot).where(AcessoriasDeliverySnapshot.external_delivery_id == "5003")
    )
    statuses = db_session.scalars(select(FiscalObligationStatus)).all()

    assert task_snapshot is not None
    assert task_snapshot.external_type == "T"
    assert len(statuses) == 1
    assert result.summary["tasks_skipped"] == 1
