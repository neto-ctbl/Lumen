from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.app.models.audit_log import AuditLog
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio.contracts import (
    DominioCnpjStatus,
    DominioDocumentContract,
    DominioEvidenceSource,
    DominioParserConfidence,
    DominioPayrollBlock,
    DominioPayrollBlockType,
    DominioPayrollCompany,
    DominioPayrollReport,
    DominioPayrollRubric,
    DominioPayrollSection,
    DominioPayrollSectionType,
    DominioPayrollSignalEvidence,
    DominioPayrollWarning,
    DominioPayrollWarningCode,
)
from backend.app.services.integrations.dominio.importer import import_dominio_payroll_file


def _create_org(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _create_company(db_session, organization: Organization, *, cnpj: str) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social=f"Empresa {cnpj}",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _write_fake_pdf(tmp_path: Path, name: str = "Resumo_Mensal_05-2026.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(b"%PDF-1.4\nsynthetic-dominio-payload\n")
    return path


def _write_manifest(
    pdf_path: Path,
    *,
    selection_scope: str | None = None,
    source_filter_name: str | None = None,
    target_company_count: int | None = None,
    target_list_sha256: str | None = None,
) -> None:
    payload: dict[str, object] = {}
    if selection_scope is not None:
        payload["selection_scope"] = selection_scope
    if source_filter_name is not None:
        payload["source_filter_name"] = source_filter_name
    if target_company_count is not None:
        payload["target_company_count"] = target_company_count
    if target_list_sha256 is not None:
        payload["target_list_sha256"] = target_list_sha256
    pdf_path.with_suffix(".manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_warning(code: DominioPayrollWarningCode, message: str = "warning") -> DominioPayrollWarning:
    return DominioPayrollWarning(code=code, message=message, physical_page_number=1)


def _make_company(
    *,
    company_code: str,
    company_name: str,
    company_cnpj: str | None,
    cnpj_status: DominioCnpjStatus,
    source_competence: str = "2026-05",
    assessment_competence: str = "2026-06",
    has_employee: bool = True,
    has_pro_labore: bool = False,
    has_autonomous: bool = False,
    has_inss: bool = True,
    has_fgts: bool = True,
    confidence: DominioParserConfidence = DominioParserConfidence.HIGH,
    warnings: tuple[DominioPayrollWarning, ...] = (),
) -> DominioPayrollCompany:
    rubric_codes = ["1", "998", "996"] if has_employee else ["100", "843"]
    rubrics = (
        DominioPayrollRubric(
            code=rubric_codes[0],
            original_name="HORAS NORMAIS" if has_employee else "PRO-LABORE",
            normalized_name="horas normais" if has_employee else "pro labore",
            contributors_count=1,
            informed_value_raw="220:00",
            informed_value_kind="HOURS",  # type: ignore[arg-type]
            informed_value_decimal=None,
            informed_value_minutes=13200,
            calculated_value=Decimal("3615.81"),
            marked_with_asterisk=False,
            section=DominioPayrollSectionType.EARNINGS,
            block_type=DominioPayrollBlockType.MONTHLY_PAYROLL,
            physical_page_number=1,
            line_order=1,
            warnings=(),
        ),
    )
    section = DominioPayrollSection(
        section_type=DominioPayrollSectionType.EARNINGS,
        physical_page_numbers=(1,),
        line_orders=(1,),
        declared_total=Decimal("3615.81"),
        calculated_total=Decimal("3615.81"),
        rubric_codes=(rubric_codes[0],),
        warnings=(),
    )
    block = DominioPayrollBlock(
        block_type=DominioPayrollBlockType.MONTHLY_PAYROLL,
        description="Folha Mensal",
        source_competence=source_competence,
        event_date=None,
        payment_date=None,
        sections=(section,),
        rubrics=rubrics,
        declared_totals={"EARNINGS": Decimal("3615.81"), "DEDUCTIONS": Decimal("783.52"), "INFORMATIONAL": Decimal("159.58")},
        warnings=(),
    )
    signal_sources = (
        DominioPayrollSignalEvidence("has_payroll", True, tuple(sorted(set(rubric_codes)))),
        DominioPayrollSignalEvidence("has_employee", has_employee, ("1", "998", "996") if has_employee else ()),
        DominioPayrollSignalEvidence("has_pro_labore", has_pro_labore, ("100",) if has_pro_labore else ()),
        DominioPayrollSignalEvidence("has_autonomous", has_autonomous, ("235", "858") if has_autonomous else ()),
        DominioPayrollSignalEvidence("has_inss", has_inss, ("843", "998") if has_inss else ()),
        DominioPayrollSignalEvidence("has_fgts", has_fgts, ("996",) if has_fgts else ()),
        DominioPayrollSignalEvidence("has_termination", False, ()),
        DominioPayrollSignalEvidence("has_vacation", False, ()),
        DominioPayrollSignalEvidence("has_leave", False, ()),
    )
    return DominioPayrollCompany(
        dominio_company_code=company_code,
        company_cnpj=company_cnpj,
        company_cnpj_raw=company_cnpj,
        company_cnpj_status=cnpj_status,
        company_name=company_name,
        source_payroll_competence=source_competence,
        assessment_competence=assessment_competence,
        calculation_type="Folha Mensal e Complementar",
        physical_page_numbers=(1,),
        declared_page_numbers=(1,),
        declared_page_count=1,
        blocks=(block,),
        rubrics=rubrics,
        has_payroll=True,
        has_employee=has_employee,
        has_pro_labore=has_pro_labore,
        has_autonomous=has_autonomous,
        has_inss=has_inss,
        has_fgts=has_fgts,
        has_termination=False,
        has_vacation=False,
        has_leave=False,
        gross_total=Decimal("3615.81"),
        discount_total=Decimal("783.52"),
        informative_total=Decimal("159.58"),
        net_total=Decimal("2832.29"),
        raw_text="sanitized raw text only",
        confidence=confidence,
        warnings=warnings,
        signal_sources=signal_sources,
    )


def _make_report(*companies: DominioPayrollCompany, warnings: tuple[DominioPayrollWarning, ...] = ()) -> DominioPayrollReport:
    return DominioPayrollReport(
        source_file_name="Resumo_Mensal_05-2026.pdf",
        source=DominioDocumentContract.DOMINIO_FOLHA_RESUMO,
        evidence_source=DominioEvidenceSource.DOMINIO_FOLHA_PDF,
        parser_version="dominio-payroll-s9.1",
        physical_page_count=max((max(company.physical_page_numbers) for company in companies), default=0),
        detected_source_competences=tuple(sorted({company.source_payroll_competence for company in companies if company.source_payroll_competence})),
        detected_assessment_competences=tuple(sorted({company.assessment_competence for company in companies if company.assessment_competence})),
        companies=companies,
        warnings=warnings,
    )


def test_dry_run_executes_parser_without_writes(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-dry-run")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    called = {"value": 0}

    def fake_parser(path: Path) -> DominioPayrollReport:
        assert path == file_path
        called["value"] += 1
        return _make_report(_make_company(company_code="0001", company_name="Empresa A", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID))

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        dry_run=True,
        parser_callable=fake_parser,
    )

    assert called["value"] == 1
    assert result.status == "DRY_RUN"
    assert result.selection_scope == "UNKNOWN"
    assert db_session.scalars(select(DominioPayrollImport)).all() == []
    assert db_session.scalars(select(DominioPayrollCompanyMovement)).all() == []
    assert db_session.scalars(select(FiscalEvidence)).all() == []
    assert db_session.scalars(select(FiscalPeriod)).all() == []
    assert db_session.scalars(select(IntegrationSyncRun)).all() == []
    assert db_session.scalars(select(AuditLog)).all() == []


def test_valid_import_creates_import_movements_evidences_period_sync_and_audit(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-valid")
    company = _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0001", company_name="Empresa A", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    movement = db_session.scalar(select(DominioPayrollCompanyMovement))
    evidence = db_session.scalar(select(FiscalEvidence))
    period = db_session.scalar(select(FiscalPeriod))
    sync_run = db_session.scalar(select(IntegrationSyncRun))
    audit_logs = db_session.scalars(select(AuditLog).order_by(AuditLog.id)).all()

    assert result.status == "COMPLETED"
    assert payroll_import is not None
    assert payroll_import.selection_scope == "UNKNOWN"
    assert movement is not None
    assert evidence is not None
    assert period is not None
    assert sync_run is not None
    assert movement.external_company_id == company.id
    assert movement.source_payroll_competence == datetime(2026, 5, 1).date()
    assert movement.assessment_competence == datetime(2026, 6, 1).date()
    assert period.competencia == "2026-06"
    assert payroll_import.assessment_period_id == period.id
    assert evidence.period_id == period.id
    assert evidence.company_id == company.id
    assert evidence.source == "DOMINIO_FOLHA_PDF"
    assert evidence.raw_payload is not None
    assert evidence.raw_payload["signals"]["has_employee"] is True
    assert sync_run.status == "SUCCESS"
    assert payroll_import.total_matched == 1
    assert payroll_import.total_unmatched == 0
    assert movement.net_total == Decimal("2832.29")
    assert movement.rubrics_summary["schema_version"] == 2
    assert movement.rubrics_summary["monetary_categories"]["employee_remuneration"]["amount"] == "3615.81"
    assert json.dumps(sync_run.summary, sort_keys=True).find("raw_text") == -1
    assert "12345678000195" not in json.dumps(sync_run.summary, sort_keys=True)
    assert "sanitized raw text only" not in json.dumps([log.event_metadata for log in audit_logs], sort_keys=True)
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == 0


def test_unmatched_import_becomes_manual_review_without_creating_evidence(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-unmatched")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0002", company_name="Empresa B", company_cnpj="22345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    movement = db_session.scalar(select(DominioPayrollCompanyMovement))
    assert result.status == "MANUAL_REVIEW"
    assert movement is not None
    assert movement.external_company_id is None
    assert movement.match_status == "UNMATCHED"
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 0


def test_invalid_and_missing_cnpj_do_not_abort_batch(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-invalid-missing")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0003", company_name="Empresa C", company_cnpj="123", cnpj_status=DominioCnpjStatus.INVALID, has_employee=False, has_pro_labore=True, has_fgts=False),
        _make_company(company_code="0004", company_name="Empresa D", company_cnpj=None, cnpj_status=DominioCnpjStatus.MISSING, has_employee=False, has_pro_labore=True, has_fgts=False),
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    assert result.status == "MANUAL_REVIEW"
    assert result.total_invalid_cnpj == 1
    assert result.total_missing_cnpj == 1
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollCompanyMovement)) == 2
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 0


def test_duplicate_import_is_no_op_and_does_not_duplicate_movements_or_evidences(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-duplicate")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0005", company_name="Empresa E", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    first = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )
    second = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    assert first.duplicate is False
    assert second.duplicate is True
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollImport)) == 1
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollCompanyMovement)) == 1
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 1
    assert db_session.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.event_type == "DOMINIO_PAYROLL_IMPORT_DUPLICATE")
    ) == 1


def test_same_hash_can_be_imported_by_different_orgs(db_session, tmp_path: Path) -> None:
    first_org = _create_org(db_session, "org-dominio-org-a")
    second_org = _create_org(db_session, "org-dominio-org-b")
    _create_company(db_session, first_org, cnpj="12345678000195")
    _create_company(db_session, second_org, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0006", company_name="Empresa F", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    import_dominio_payroll_file(db_session, organization=first_org, file_path=file_path, parser_callable=lambda path: report)
    import_dominio_payroll_file(db_session, organization=second_org, file_path=file_path, parser_callable=lambda path: report)

    assert db_session.scalar(select(func.count()).select_from(DominioPayrollImport)) == 2
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 2


def test_fatal_parser_failure_marks_import_failed_without_partial_writes(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-failed")
    file_path = _write_fake_pdf(tmp_path)

    with pytest.raises(RuntimeError):
        import_dominio_payroll_file(
            db_session,
            organization=organization,
            file_path=file_path,
            parser_callable=lambda path: (_ for _ in ()).throw(RuntimeError("PDF sem camada textual.")),
        )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    sync_run = db_session.scalar(select(IntegrationSyncRun))
    assert payroll_import is not None
    assert payroll_import.status == "FAILED"
    assert payroll_import.total_errors == 1
    assert payroll_import.errors[0]["code"] == "RUNTIMEERROR"
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollCompanyMovement)) == 0
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 0
    assert sync_run is not None
    assert sync_run.status == "FAILED"


def test_retry_reuses_failed_import_row_without_duplication(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-retry")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0007", company_name="Empresa G", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )
    state = {"calls": 0}

    def flaky_parser(path: Path) -> DominioPayrollReport:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("Falha sintetica")
        return report

    with pytest.raises(RuntimeError):
        import_dominio_payroll_file(
            db_session,
            organization=organization,
            file_path=file_path,
            parser_callable=flaky_parser,
        )

    failed_import = db_session.scalar(select(DominioPayrollImport))
    assert failed_import is not None

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=flaky_parser,
    )

    completed_import = db_session.scalar(select(DominioPayrollImport))
    assert result.status == "COMPLETED"
    assert completed_import is not None
    assert completed_import.id == failed_import.id
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollImport)) == 1
    assert db_session.scalar(select(func.count()).select_from(DominioPayrollCompanyMovement)) == 1
    assert db_session.scalar(select(func.count()).select_from(FiscalEvidence)) == 1


def test_import_reads_factor_r_manifest_metadata(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-manifest-factor-r")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(
        file_path,
        selection_scope="FACTOR_R",
        source_filter_name="Fator R",
        target_company_count=25,
        target_list_sha256="a" * 64,
    )
    report = _make_report(
        _make_company(company_code="0008", company_name="Empresa H", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert result.selection_scope == "FACTOR_R"
    assert result.source_filter_name == "Fator R"
    assert result.target_company_count == 25
    assert result.target_list_sha256 == "a" * 64
    assert payroll_import is not None
    assert payroll_import.selection_scope == "FACTOR_R"
    assert payroll_import.source_filter_name == "Fator R"
    assert payroll_import.target_company_count == 25
    assert payroll_import.target_list_sha256 == "a" * 64
    assert payroll_import.raw_metadata["manifest"]["selection_scope"] == "FACTOR_R"


def test_import_normalizes_legacy_ativas_manifest(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-manifest-ativas")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(file_path, selection_scope="ATIVAS", source_filter_name="Ativas")
    report = _make_report(
        _make_company(company_code="0009", company_name="Empresa I", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert payroll_import is not None
    assert payroll_import.selection_scope == "ACTIVE_COMPANIES"
    assert payroll_import.source_filter_name == "Ativas"
    assert payroll_import.raw_metadata["manifest"]["original_selection_scope"] == "ATIVAS"


def test_import_infers_active_companies_from_ativas_filter_without_selection_scope(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-manifest-ativas-inferred")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(file_path, source_filter_name="Ativas")
    report = _make_report(
        _make_company(company_code="0011", company_name="Empresa K", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        dry_run=True,
        parser_callable=lambda path: report,
    )

    assert result.selection_scope == "ACTIVE_COMPANIES"
    assert result.source_filter_name == "Ativas"
    assert result.target_company_count is None
    assert result.target_list_sha256 is None


def test_active_companies_manifest_discards_factor_r_target_metadata(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-manifest-ativas-metadata")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(
        file_path,
        selection_scope="ACTIVE_COMPANIES",
        source_filter_name="Ativas",
        target_company_count=43,
        target_list_sha256="a" * 64,
    )
    report = _make_report(
        _make_company(company_code="0012", company_name="Empresa L", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert result.selection_scope == "ACTIVE_COMPANIES"
    assert result.target_company_count is None
    assert result.target_list_sha256 is None
    assert payroll_import is not None
    assert payroll_import.selection_scope == "ACTIVE_COMPANIES"
    assert payroll_import.target_company_count is None
    assert payroll_import.target_list_sha256 is None


def test_import_without_manifest_defaults_to_unknown_scope(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-manifest-unknown")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(company_code="0010", company_name="Empresa J", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert result.selection_scope == "UNKNOWN"
    assert payroll_import is not None
    assert payroll_import.selection_scope == "UNKNOWN"
    assert payroll_import.source_filter_name is None


def test_factor_r_manifest_with_consistent_target_count_completes_without_scope_warning(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-factor-r-consistent")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(
        file_path,
        selection_scope="FACTOR_R",
        source_filter_name="Fator R",
        target_company_count=1,
        target_list_sha256="b" * 64,
    )
    report = _make_report(
        _make_company(company_code="0013", company_name="Empresa M", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert result.status == "COMPLETED"
    assert payroll_import is not None
    assert payroll_import.status == "COMPLETED"
    assert [warning["code"] for warning in payroll_import.warnings] == []


def test_factor_r_manifest_with_zero_target_count_and_parsed_companies_forces_manual_review(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-factor-r-mismatch")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    _write_manifest(
        file_path,
        selection_scope="FACTOR_R",
        source_filter_name="Fator R",
        target_company_count=0,
        target_list_sha256="c" * 64,
    )
    report = _make_report(
        _make_company(company_code="0014", company_name="Empresa N", company_cnpj="12345678000195", cnpj_status=DominioCnpjStatus.VALID)
    )

    result = import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    payroll_import = db_session.scalar(select(DominioPayrollImport))
    assert result.status == "MANUAL_REVIEW"
    assert payroll_import is not None
    assert payroll_import.status == "MANUAL_REVIEW"
    assert [warning["code"] for warning in payroll_import.warnings] == ["FACTOR_R_TARGET_SCOPE_MISMATCH"]
    assert payroll_import.warnings[0]["context"] == {
        "target_company_count": 0,
        "parsed_distinct_company_count": 1,
    }
