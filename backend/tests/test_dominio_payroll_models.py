from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from backend.app.models import DominioPayrollCompanyMovement, DominioPayrollImport, FiscalPeriod, Organization


def _create_org(db_session, slug: str = "org-dominio-models") -> Organization:
    organization = Organization(name="Org Dominio", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _create_period(db_session, organization: Organization, competencia: str = "2026-06") -> FiscalPeriod:
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


def _create_import(db_session, organization: Organization, *, file_sha256: str = "a" * 64) -> DominioPayrollImport:
    payroll_import = DominioPayrollImport(
        organization_id=organization.id,
        assessment_period_id=None,
        source="DOMINIO_FOLHA_RESUMO",
        evidence_source="DOMINIO_FOLHA_PDF",
        parser_version="dominio-payroll-s9.1",
        status="PROCESSING",
        source_file_name="Resumo_Mensal_05-2026.pdf",
        source_file_path="scripts/collectors/dominio/Relatorios_Dominio/Resumo_Mensal_05-2026.pdf",
        file_sha256=file_sha256,
        file_size_bytes=1024,
        physical_page_count=1,
        source_competences=["2026-05"],
        assessment_competences=["2026-06"],
        warnings=[],
        errors=[],
        raw_metadata={"fixture": True},
    )
    db_session.add(payroll_import)
    db_session.flush()
    return payroll_import


def test_dominio_payroll_tables_exist_and_indexes_are_present(db_session) -> None:
    inspector = inspect(db_session.bind)
    tables = set(inspector.get_table_names())

    assert {"dominio_payroll_imports", "dominio_payroll_company_movements"}.issubset(tables)

    import_indexes = {item["name"] for item in inspector.get_indexes("dominio_payroll_imports")}
    movement_indexes = {item["name"] for item in inspector.get_indexes("dominio_payroll_company_movements")}
    assert "ix_dominio_payroll_imports_org_imported" in import_indexes
    assert "ix_dominio_payroll_imports_org_status" in import_indexes
    assert "ix_dominio_payroll_imports_file_sha256" in import_indexes
    assert "ix_dominio_payroll_movements_org_match_status" in movement_indexes
    assert "ix_dominio_payroll_movements_org_period" in movement_indexes
    assert "ix_dominio_payroll_movements_movement_hash" in movement_indexes


def test_dominio_payroll_import_unique_per_org_and_hash(db_session) -> None:
    organization = _create_org(db_session)
    _create_import(db_session, organization, file_sha256="b" * 64)

    duplicate = DominioPayrollImport(
        organization_id=organization.id,
        assessment_period_id=None,
        source="DOMINIO_FOLHA_RESUMO",
        evidence_source="DOMINIO_FOLHA_PDF",
        parser_version="dominio-payroll-s9.1",
        status="PROCESSING",
        source_file_name="other.pdf",
        source_file_path=None,
        file_sha256="b" * 64,
        file_size_bytes=2048,
        physical_page_count=2,
        source_competences=["2026-05"],
        assessment_competences=["2026-06"],
        warnings=[],
        errors=[],
        raw_metadata={},
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_dominio_payroll_import_same_hash_is_allowed_in_other_org(db_session) -> None:
    first_org = _create_org(db_session, "org-dominio-models-a")
    second_org = _create_org(db_session, "org-dominio-models-b")

    _create_import(db_session, first_org, file_sha256="c" * 64)
    _create_import(db_session, second_org, file_sha256="c" * 64)

    assert db_session.query(DominioPayrollImport).count() == 2


def test_dominio_payroll_movement_unique_per_import_and_source_company_key(db_session) -> None:
    organization = _create_org(db_session)
    period = _create_period(db_session, organization)
    payroll_import = _create_import(db_session, organization, file_sha256="d" * 64)
    first = DominioPayrollCompanyMovement(
        import_id=payroll_import.id,
        organization_id=organization.id,
        external_company_id=None,
        fiscal_period_id=period.id,
        source_company_key="0001|12345678000195|2026-05",
        dominio_company_code="0001",
        company_cnpj="12345678000195",
        source_company_name="Empresa A",
        source_payroll_competence=date(2026, 5, 1),
        assessment_competence=date(2026, 6, 1),
        match_status="MATCHED",
        parser_confidence="HIGH",
        calculation_type="Folha Mensal e Complementar",
        has_payroll=True,
        has_employee=True,
        has_pro_labore=False,
        has_autonomous=False,
        has_inss=True,
        has_fgts=True,
        has_termination=False,
        has_vacation=False,
        has_leave=False,
        gross_total=Decimal("1000.00"),
        discount_total=Decimal("100.00"),
        informative_total=Decimal("50.00"),
        net_total=Decimal("900.00"),
        source_page_start=1,
        source_page_end=1,
        source_page_count=1,
        source_page_numbers=[1],
        declared_page_count=1,
        movement_hash="e" * 64,
        rubrics_summary={"schema_version": 1, "codes": ["1"]},
        warnings=[],
        raw_text="sanitized raw text",
    )
    db_session.add(first)
    db_session.flush()

    duplicate = DominioPayrollCompanyMovement(
        import_id=payroll_import.id,
        organization_id=organization.id,
        external_company_id=None,
        fiscal_period_id=period.id,
        source_company_key="0001|12345678000195|2026-05",
        dominio_company_code="0001",
        company_cnpj="12345678000195",
        source_company_name="Empresa A",
        source_payroll_competence=date(2026, 5, 1),
        assessment_competence=date(2026, 6, 1),
        match_status="MATCHED",
        parser_confidence="HIGH",
        calculation_type="Folha Mensal e Complementar",
        has_payroll=True,
        has_employee=True,
        has_pro_labore=False,
        has_autonomous=False,
        has_inss=True,
        has_fgts=True,
        has_termination=False,
        has_vacation=False,
        has_leave=False,
        gross_total=Decimal("1000.00"),
        discount_total=Decimal("100.00"),
        informative_total=Decimal("50.00"),
        net_total=Decimal("900.00"),
        source_page_start=1,
        source_page_end=1,
        source_page_count=1,
        source_page_numbers=[1],
        declared_page_count=1,
        movement_hash="f" * 64,
        rubrics_summary={"schema_version": 1, "codes": ["1"]},
        warnings=[],
        raw_text="sanitized raw text",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_dominio_payroll_model_exports_are_registered() -> None:
    from backend.app import models

    assert hasattr(models, "DominioPayrollImport")
    assert hasattr(models, "DominioPayrollCompanyMovement")
