from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.services.integrations.sittax.sync import MATCHED, UNMATCHED, build_fixture_sittax_client, sync_sittax_apuracoes


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def _seed_organization(db_session) -> Organization:
    organization = Organization(name="Org Sittax", slug="org-sittax")
    db_session.add(organization)
    db_session.flush()
    return organization


def _seed_period(db_session, organization: Organization, competencia: str = "2026-06") -> FiscalPeriod:
    period = FiscalPeriod(
        organization_id=organization.id,
        year=int(competencia[:4]),
        month=int(competencia[5:7]),
        competencia=competencia,
        status="OPEN",
    )
    db_session.add(period)
    db_session.flush()
    return period


def _seed_external_company(db_session, organization: Organization, *, cnpj: str = "12345678000195") -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social="Empresa Local",
        nome_fantasia="Local",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _seed_company_snapshot(
    db_session,
    organization: Organization,
    *,
    company_id: int | None,
    cnpj: str,
    sittax_company_id: str,
    match_status: str,
) -> SittaxCompanySnapshot:
    snapshot = SittaxCompanySnapshot(
        organization_id=organization.id,
        company_id=company_id,
        sittax_company_id=sittax_company_id,
        cnpj=cnpj,
        legal_name="Empresa Sittax",
        trade_name="Empresa",
        state_registration=None,
        state="GO",
        status="HOMOLOGADA",
        homologated=True,
        cash_regime=False,
        match_status=match_status,
        raw_payload={"id": sittax_company_id},
        first_seen_at=_now(),
        last_seen_at=_now(),
    )
    db_session.add(snapshot)
    db_session.flush()
    return snapshot


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _fixture_client():
    return build_fixture_sittax_client(apuracao_fixture=FIXTURES_DIR / "apuracao_success.json")


def test_sync_sittax_apuracoes_creates_snapshot_and_is_idempotent(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(
        db_session,
        organization,
        company_id=company.id,
        cnpj=company.cnpj,
        sittax_company_id="emp-sittax-001",
        match_status=MATCHED,
    )
    _seed_company_snapshot(
        db_session,
        organization,
        company_id=None,
        cnpj="11111111000111",
        sittax_company_id="emp-sittax-002",
        match_status=UNMATCHED,
    )

    first = sync_sittax_apuracoes(
        db_session,
        organization=organization,
        period=period.competencia,
        client=_fixture_client(),
    )
    second = sync_sittax_apuracoes(
        db_session,
        organization=organization,
        period=period.competencia,
        client=_fixture_client(),
    )

    snapshots = db_session.scalars(select(SittaxApuracaoSnapshot)).all()
    runs = db_session.scalars(select(IntegrationSyncRun).where(IntegrationSyncRun.job_name == "sync_sittax_apuracoes")).all()

    assert first.status == "SUCCESS"
    assert first.summary["companies_selected"] == 1
    assert first.summary["companies_skipped_unmatched"] == 1
    assert first.summary["snapshots_created"] == 1
    assert second.summary["snapshots_created"] == 0
    assert second.summary["snapshots_unchanged"] == 1
    assert len(snapshots) == 1
    assert snapshots[0].external_company_id == company.id
    assert snapshots[0].fiscal_period_id == period.id
    assert snapshots[0].company_name == "EMPRESA EXEMPLO A LTDA"
    assert snapshots[0].factor_r_percent is not None
    assert len(runs) == 2


def test_sync_sittax_apuracoes_supports_dry_run_without_writes(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(
        db_session,
        organization,
        company_id=company.id,
        cnpj=company.cnpj,
        sittax_company_id="emp-sittax-001",
        match_status=MATCHED,
    )

    result = sync_sittax_apuracoes(
        db_session,
        organization=organization,
        period=period.competencia,
        dry_run=True,
        client=_fixture_client(),
    )

    assert result.status == "DRY_RUN"
    assert result.run is None
    assert db_session.scalars(select(SittaxApuracaoSnapshot)).all() == []
    assert db_session.scalars(select(IntegrationSyncRun)).all() == []


def test_sync_sittax_apuracoes_requires_existing_period_and_specific_company_match(db_session) -> None:
    organization = _seed_organization(db_session)
    company = _seed_external_company(db_session, organization)

    with pytest.raises(ValueError, match="Fiscal period"):
        sync_sittax_apuracoes(
            db_session,
            organization=organization,
            period="2026-06",
            dry_run=True,
            client=_fixture_client(),
        )

    _seed_period(db_session, organization)
    with pytest.raises(ValueError, match="Matched Sittax company snapshot not found"):
        sync_sittax_apuracoes(
            db_session,
            organization=organization,
            period="2026-06",
            company_id=company.id,
            dry_run=True,
            client=_fixture_client(),
        )
