from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.models.sittax_difal_snapshot import SittaxDifalSnapshot
from backend.app.models.sittax_fiscal_document_snapshot import SittaxFiscalDocumentSnapshot
from backend.app.models.sittax_task_snapshot import SittaxTaskSnapshot


def _seed_dependencies(db_session) -> tuple[Organization, ExternalCompany, FiscalPeriod, SittaxCompanySnapshot, SittaxApuracaoSnapshot]:
    now = datetime.now(timezone.utc)
    organization = Organization(name="Org Sittax", slug="org-sittax-op")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="12345678000195",
        razao_social="Empresa Local",
        nome_fantasia="Empresa",
        active=True,
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
    company_snapshot = SittaxCompanySnapshot(
        organization_id=organization.id,
        company_id=company.id,
        sittax_company_id="emp-1",
        cnpj=company.cnpj,
        legal_name="Empresa Sittax",
        trade_name="Empresa",
        state="GO",
        status="HOMOLOGADA",
        homologated=True,
        cash_regime=False,
        match_status="MATCHED",
        raw_payload={"id": "emp-1"},
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(company_snapshot)
    db_session.flush()
    apuracao_snapshot = SittaxApuracaoSnapshot(
        organization_id=organization.id,
        sittax_company_snapshot_id=company_snapshot.id,
        external_company_id=company.id,
        fiscal_period_id=period.id,
        sittax_apuracao_id="apur-1",
        company_cnpj=company.cnpj,
        company_name="Empresa Sittax",
        period_reference="2026-06",
        is_transmitted=False,
        transmission_in_progress=False,
        raw_payload={"id": "apur-1"},
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(apuracao_snapshot)
    db_session.flush()
    return organization, company, period, company_snapshot, apuracao_snapshot


def test_operational_snapshot_tables_exist(db_session) -> None:
    inspector = inspect(db_session.get_bind())

    assert "sittax_difal_snapshots" in inspector.get_table_names()
    assert "sittax_fiscal_document_snapshots" in inspector.get_table_names()
    assert "sittax_task_snapshots" in inspector.get_table_names()


def test_operational_snapshot_unique_constraints_hold(db_session) -> None:
    now = datetime.now(timezone.utc)
    organization, company, period, company_snapshot, apuracao_snapshot = _seed_dependencies(db_session)
    db_session.add(
        SittaxDifalSnapshot(
            organization_id=organization.id,
            sittax_company_snapshot_id=company_snapshot.id,
            sittax_apuracao_snapshot_id=apuracao_snapshot.id,
            external_company_id=company.id,
            fiscal_period_id=period.id,
            company_cnpj=company.cnpj,
            period_reference="2026-06",
            has_guide=False,
            total_amount=Decimal("0.00"),
            raw_payload={"id": "difal-1"},
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        SittaxDifalSnapshot(
            organization_id=organization.id,
            sittax_company_snapshot_id=company_snapshot.id,
            sittax_apuracao_snapshot_id=apuracao_snapshot.id,
            external_company_id=company.id,
            fiscal_period_id=period.id,
            company_cnpj=company.cnpj,
            period_reference="2026-06",
            has_guide=False,
            total_amount=Decimal("0.00"),
            raw_payload={"id": "difal-2"},
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_task_snapshot_allows_nullable_links_for_unmatched_company(db_session) -> None:
    organization, _, period, company_snapshot, apuracao_snapshot = _seed_dependencies(db_session)
    now = datetime.now(timezone.utc)
    snapshot = SittaxTaskSnapshot(
        organization_id=organization.id,
        source_task_key="task-1",
        sittax_task_id="task-1",
        sittax_company_snapshot_id=None,
        external_company_id=None,
        fiscal_period_id=None,
        task_name="Transmitir DAS",
        company_cnpj=None,
        period_reference=None,
        raw_payload={"id": "task-1"},
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(snapshot)
    db_session.flush()

    document = SittaxFiscalDocumentSnapshot(
        organization_id=organization.id,
        sittax_company_snapshot_id=company_snapshot.id,
        sittax_apuracao_snapshot_id=apuracao_snapshot.id,
        external_company_id=None,
        fiscal_period_id=period.id,
        source_document_key="doc-1",
        document_direction="ENTRADA",
        period_reference="2026-06",
        total_amount=Decimal("10.00"),
        cfops=["1102"],
        raw_payload={"id": "doc-1"},
        first_seen_at=now,
        last_seen_at=now,
    )
    db_session.add(document)
    db_session.flush()

    assert snapshot.id is not None
    assert document.id is not None
