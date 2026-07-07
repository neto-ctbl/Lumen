from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from backend.app.core.enums import ActivityType, Department, FISCAL_REGIME_LABELS, FiscalRegime, ReconciliationStatus
from backend.app.models import ExternalCompany, FiscalObligation, FiscalObligationStatus, FiscalPeriod, Organization


def _create_organization(db_session, slug: str = "org-s4") -> Organization:
    organization = Organization(name="Org S4", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _create_company(db_session, organization: Organization, cnpj: str = "12345678000190") -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social="Empresa Fiscal LTDA",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _create_period(db_session, organization: Organization, competencia: str = "2026-06") -> FiscalPeriod:
    period = FiscalPeriod(
        organization_id=organization.id,
        year=2026,
        month=6,
        competencia=competencia,
        status="OPEN",
    )
    db_session.add(period)
    db_session.flush()
    return period


def _create_obligation(db_session, code: str = "DAS_TEST") -> FiscalObligation:
    obligation = FiscalObligation(
        code=code,
        name=code,
        category="TEST",
        department_default=Department.FISCAL.value,
        source_priority=[],
        active=True,
    )
    db_session.add(obligation)
    db_session.flush()
    return obligation


def test_s4_tables_exist(prepared_test_database: None, test_settings) -> None:
    db_engine = create_engine(test_settings.test_database_url, future=True)
    try:
        tables = set(inspect(db_engine).get_table_names())
    finally:
        db_engine.dispose()

    assert {
        "external_companies",
        "company_activity_types",
        "fiscal_periods",
        "fiscal_obligations",
        "fiscal_obligation_rules",
        "fiscal_obligation_statuses",
        "fiscal_evidences",
        "fiscal_alerts",
        "fiscal_installments",
        "integration_accounts",
        "integration_sync_runs",
        "watcher_file_events",
    }.issubset(tables)


def test_external_companies_support_soft_delete(db_session) -> None:
    organization = _create_organization(db_session)
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="11222333000181",
        razao_social="Empresa Soft Delete",
        active=False,
        deleted_at_econtrole=datetime.now(timezone.utc),
        sync_status="SOFT_DELETED",
    )
    db_session.add(company)
    db_session.flush()

    loaded = db_session.get(ExternalCompany, company.id)
    assert loaded is not None
    assert loaded.organization_id == organization.id
    assert loaded.active is False
    assert loaded.deleted_at_econtrole is not None


def test_fiscal_periods_unique_per_org_and_competencia(db_session) -> None:
    organization = _create_organization(db_session)
    _create_period(db_session, organization, "2026-06")

    duplicate = FiscalPeriod(
        organization_id=organization.id,
        year=2026,
        month=6,
        competencia="2026-06",
        status="OPEN",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_fiscal_obligation_statuses_unique_company_period_obligation(db_session) -> None:
    organization = _create_organization(db_session)
    company = _create_company(db_session, organization)
    period = _create_period(db_session, organization)
    obligation = _create_obligation(db_session)

    first = FiscalObligationStatus(
        organization_id=organization.id,
        company_id=company.id,
        period_id=period.id,
        obligation_id=obligation.id,
        status=ReconciliationStatus.PENDENTE.value,
        responsible_department=Department.FISCAL.value,
    )
    db_session.add(first)
    db_session.flush()

    duplicate = FiscalObligationStatus(
        organization_id=organization.id,
        company_id=company.id,
        period_id=period.id,
        obligation_id=obligation.id,
        status=ReconciliationStatus.CONFIRMADO_API.value,
        responsible_department=Department.FISCAL.value,
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_backend_app_models_exports_new_s4_models() -> None:
    from backend.app import models

    for name in (
        "CompanyActivityType",
        "ExternalCompany",
        "FiscalAlert",
        "FiscalEvidence",
        "FiscalInstallment",
        "FiscalObligation",
        "FiscalObligationRule",
        "FiscalObligationStatus",
        "FiscalPeriod",
        "IntegrationAccount",
        "IntegrationSyncRun",
        "WatcherFileEvent",
    ):
        assert hasattr(models, name)


def test_required_enums_exist() -> None:
    assert [status.value for status in ReconciliationStatus] == [
        "CONFIRMADO_ARQUIVO_ACESSORIAS",
        "CONFIRMADO_API",
        "CONFIRMADO_ARQUIVO",
        "PENDENTE",
        "PENDENTE_SEM_ARQUIVO",
        "DIVERGENTE",
        "DISPENSADO_AUTOMATICAMENTE",
        "NAO_APLICAVEL",
        "BAIXA_CONFIANCA",
        "CONFERENCIA_MANUAL",
    ]
    assert [department.value for department in Department] == ["FISCAL", "DP", "COMPARTILHADO", "SISTEMA"]
    assert [activity.value for activity in ActivityType] == [
        "COMERCIO",
        "INDUSTRIA",
        "SERVICOS",
        "SERVICOS_MEDICOS_ODONTOLOGICOS",
        "SERVICOS_IMOBILIARIOS",
        "TEMPLO_RELIGIOSO",
    ]
    assert [regime.value for regime in FiscalRegime] == [
        "SIMPLES_NACIONAL",
        "MEI",
        "LUCRO_PRESUMIDO",
        "LUCRO_REAL",
        "IMUNE_ISENTA",
    ]
    assert FISCAL_REGIME_LABELS[FiscalRegime.IMUNE_ISENTA] == "Imune/Isenta"
