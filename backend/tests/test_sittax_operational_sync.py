from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.models.sittax_difal_snapshot import SittaxDifalSnapshot
from backend.app.models.sittax_fiscal_document_snapshot import SittaxFiscalDocumentSnapshot
from backend.app.models.sittax_task_snapshot import SittaxTaskSnapshot
from backend.app.services.integrations.sittax.errors import SittaxContextMismatchError
from backend.app.services.integrations.sittax.sync import (
    MATCHED,
    _normalize_transmitted_at,
    build_fixture_sittax_client,
    sync_sittax_operational,
)


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def _seed_organization(db_session) -> Organization:
    organization = Organization(name="Org Sittax", slug="org-sittax-op")
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


def _seed_company_snapshot(db_session, organization: Organization, company: ExternalCompany) -> SittaxCompanySnapshot:
    from datetime import datetime, timezone

    snapshot = SittaxCompanySnapshot(
        organization_id=organization.id,
        company_id=company.id,
        sittax_company_id="emp-sittax-001",
        cnpj=company.cnpj,
        legal_name="Empresa Sittax",
        trade_name="Empresa",
        state="GO",
        status="HOMOLOGADA",
        homologated=True,
        cash_regime=False,
        match_status=MATCHED,
        raw_payload={"id": "emp-sittax-001"},
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(snapshot)
    db_session.flush()
    return snapshot


def _fixture_client():
    return build_fixture_sittax_client(
        apuracao_fixture=FIXTURES_DIR / "apuracao_success.json",
        difal_fixture=FIXTURES_DIR / "difal_without_guide.json",
        entry_documents_fixture=FIXTURES_DIR / "fiscal_documents_entry_page.json",
        exit_documents_fixture=FIXTURES_DIR / "fiscal_documents_exit_page.json",
        tasks_fixture=FIXTURES_DIR / "tasks_page.json",
    )


class _FakeSession:
    @contextmanager
    def exclusive(self):
        yield

    def clear_active_context(self) -> None:
        return None


class _ClientWithDifalContextLoss:
    def __init__(self) -> None:
        self.session = _FakeSession()
        self.document_calls = 0

    def authenticate_with_settings(self, settings) -> None:
        return None

    def get_apuracao(self, *, company_cnpj: str, period: str):
        from backend.app.services.integrations.sittax.mapper import map_apuracao_response

        import json

        payload = json.loads((FIXTURES_DIR / "apuracao_success.json").read_text(encoding="utf-8"))
        return map_apuracao_response(payload, requested_company_cnpj=company_cnpj, requested_period=period)

    def ensure_api_context(self, *, company_cnpj: str, period: str) -> None:
        return None

    def get_difal(self, *, company_cnpj: str, period: str):
        raise SittaxContextMismatchError("context lost")

    def paginate_fiscal_documents(self, **kwargs):
        self.document_calls += 1
        return []

    def paginate_tasks(self, **kwargs):
        return []

    def close(self) -> None:
        return None


def test_sync_sittax_operational_persists_and_is_idempotent(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(db_session, organization, company)

    first = sync_sittax_operational(
        db_session,
        organization=organization,
        period=period.competencia,
        client=_fixture_client(),
    )
    second = sync_sittax_operational(
        db_session,
        organization=organization,
        period=period.competencia,
        client=_fixture_client(),
    )

    assert first.status == "SUCCESS"
    assert first.summary["difal_snapshots_created"] == 1
    assert first.summary["document_snapshots_created"] == 4
    assert first.summary["task_snapshots_created"] == 1
    assert second.summary["difal_snapshots_created"] == 0
    assert second.summary["document_snapshots_created"] == 0
    assert second.summary["task_snapshots_created"] == 0
    assert second.summary["difal_snapshots_unchanged"] == 1
    assert second.summary["document_snapshots_unchanged"] == 4
    assert second.summary["task_snapshots_unchanged"] == 1
    assert len(db_session.scalars(select(SittaxApuracaoSnapshot)).all()) == 1
    assert len(db_session.scalars(select(SittaxDifalSnapshot)).all()) == 1
    assert len(db_session.scalars(select(SittaxFiscalDocumentSnapshot)).all()) == 4
    assert len(db_session.scalars(select(SittaxTaskSnapshot)).all()) == 1


def test_sync_sittax_operational_dry_run_does_not_create_run(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(db_session, organization, company)

    result = sync_sittax_operational(
        db_session,
        organization=organization,
        period=period.competencia,
        dry_run=True,
        client=_fixture_client(),
    )

    assert result.status == "DRY_RUN"
    assert result.run is None
    assert db_session.scalars(select(IntegrationSyncRun)).all() == []


def test_sync_sittax_operational_stops_documents_after_difal_context_loss(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(db_session, organization, company)
    client = _ClientWithDifalContextLoss()

    result = sync_sittax_operational(
        db_session,
        organization=organization,
        period=period.competencia,
        client=client,
    )

    assert result.status == "PARTIAL"
    assert result.summary["failures"] == 1
    assert len(result.errors) == 1
    assert client.document_calls == 0


def test_sync_sittax_operational_finalizes_failed_run_on_unexpected_error(db_session) -> None:
    organization = _seed_organization(db_session)
    period = _seed_period(db_session, organization)
    company = _seed_external_company(db_session, organization)
    _seed_company_snapshot(db_session, organization, company)

    class _BoomClient(_ClientWithDifalContextLoss):
        def authenticate_with_settings(self, settings) -> None:
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        sync_sittax_operational(
            db_session,
            organization=organization,
            period=period.competencia,
            client=_BoomClient(),
        )

    run = db_session.scalar(select(IntegrationSyncRun).where(IntegrationSyncRun.job_name == "sync_sittax_operational"))
    assert run is not None
    assert run.status == "FAILED"
    assert run.finished_at is not None
    assert run.error_count == 1


def test_normalize_transmitted_at_accepts_seven_digit_fractional_seconds() -> None:
    parsed = _normalize_transmitted_at("2026-07-20T14:18:41.7704169")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 7
    assert parsed.day == 20


def test_normalize_transmitted_at_accepts_short_fractional_seconds() -> None:
    parsed = _normalize_transmitted_at("2026-07-20T20:20:01.53")

    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 7
    assert parsed.day == 20
    assert parsed.microsecond == 530000
