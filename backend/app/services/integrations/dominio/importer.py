from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.dominio_payroll import (
    DominioPayrollCompanyMovement,
    DominioPayrollImport,
    DominioPayrollImportStatus,
    DominioPayrollMatchStatus,
)
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.audit import record_audit_event
from backend.app.services.integrations.dominio.contracts import (
    DominioPayrollCompany,
    DominioPayrollReport,
)
from backend.app.services.integrations.dominio.matching import match_dominio_company_by_cnpj
from backend.app.services.integrations.dominio.parser import parse_dominio_payroll_pdf
from backend.app.services.integrations.dominio.selection_scope import (
    DominioManifestSelectionMetadata,
    build_manifest_selection_metadata,
)


DOMINIO_PAYROLL_SYNC_PROVIDER = "DOMINIO_FOLHA"
DOMINIO_PAYROLL_SYNC_JOB = "import_dominio_payroll_file"
DOMINIO_PAYROLL_RUBRICS_SCHEMA_VERSION = 1
IMPORT_STARTED_EVENT = "DOMINIO_PAYROLL_IMPORT_STARTED"
IMPORT_COMPLETED_EVENT = "DOMINIO_PAYROLL_IMPORT_COMPLETED"
IMPORT_FAILED_EVENT = "DOMINIO_PAYROLL_IMPORT_FAILED"
IMPORT_DUPLICATE_EVENT = "DOMINIO_PAYROLL_IMPORT_DUPLICATE"
SYSTEM_ACTOR_TYPE = "system"
SYSTEM_ACTOR_ID = "dominio-payroll-cli"
SAFE_FILE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
RELEVANT_WARNING_CODES = {
    "PAGE_HEADER_MISSING",
    "COMPANY_HEADER_INCOMPLETE",
    "INVALID_COMPETENCE",
    "FILE_NAME_COMPETENCE_MISMATCH",
    "DECLARED_PAGE_SEQUENCE_MISMATCH",
    "CONTINUATION_PAGE_EMPTY",
    "UNKNOWN_BLOCK_HEADING",
    "RUBRIC_LINE_UNPARSED",
    "INFORMED_VALUE_UNPARSED",
    "CALCULATED_VALUE_UNPARSED",
    "SECTION_TOTAL_WITHOUT_SECTION",
    "SECTION_TOTAL_MISMATCH",
    "NET_TOTAL_MISSING",
    "MULTIPLE_COMPETENCES_IN_FILE",
    "TEXT_LAYER_MISSING",
    "NO_COMPANY_BLOCKS_FOUND",
}
FACTOR_R_TARGET_SCOPE_MISMATCH = "FACTOR_R_TARGET_SCOPE_MISMATCH"


@dataclass(frozen=True, slots=True)
class DominioPayrollImportResult:
    import_id: int | None
    duplicate: bool
    already_processing: bool
    dry_run: bool
    status: str
    selection_scope: str
    source_filter_name: str | None
    target_company_count: int | None
    target_list_sha256: str | None
    file_sha256: str
    physical_page_count: int
    total_companies: int
    total_matched: int
    total_unmatched: int
    total_invalid_cnpj: int
    total_missing_cnpj: int
    total_ambiguous: int
    total_warnings: int
    total_errors: int
    source_competences: list[str]
    assessment_competences: list[str]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "duplicate": self.duplicate,
            "already_processing": self.already_processing,
            "dry_run": self.dry_run,
            "selection_scope": self.selection_scope,
            "source_filter_name": self.source_filter_name,
            "target_company_count": self.target_company_count,
            "target_list_sha256": self.target_list_sha256,
            "file_sha256": self.file_sha256,
            "physical_page_count": self.physical_page_count,
            "source_competences": self.source_competences,
            "assessment_competences": self.assessment_competences,
            "total_companies": self.total_companies,
            "total_matched": self.total_matched,
            "total_unmatched": self.total_unmatched,
            "total_invalid_cnpj": self.total_invalid_cnpj,
            "total_missing_cnpj": self.total_missing_cnpj,
            "total_ambiguous": self.total_ambiguous,
            "total_warnings": self.total_warnings,
            "total_errors": self.total_errors,
        }


@dataclass(slots=True)
class _PreparedImportData:
    report: DominioPayrollReport
    total_companies: int
    total_matched: int
    total_unmatched: int
    total_invalid_cnpj: int
    total_missing_cnpj: int
    total_ambiguous: int
    total_warnings: int
    total_errors: int
    scope_warnings: list[dict[str, Any]]
    source_competences: list[str]
    assessment_competences: list[str]


def import_dominio_payroll_file(
    session: Session,
    *,
    organization: Organization,
    file_path: str | Path,
    dry_run: bool = False,
    actor_type: str | None = SYSTEM_ACTOR_TYPE,
    actor_id: str | None = SYSTEM_ACTOR_ID,
    parser_callable: Callable[[Path], DominioPayrollReport] = parse_dominio_payroll_pdf,
) -> DominioPayrollImportResult:
    normalized_path = Path(file_path)
    if not normalized_path.exists() or not normalized_path.is_file():
        raise FileNotFoundError(f"Payroll file was not found: {normalized_path}")

    file_sha256 = _compute_file_sha256(normalized_path)
    file_size_bytes = normalized_path.stat().st_size
    started_timer = perf_counter()
    manifest_metadata = _load_manifest_selection_metadata(normalized_path)

    existing_import = session.scalar(
        select(DominioPayrollImport).where(
            DominioPayrollImport.organization_id == organization.id,
            DominioPayrollImport.file_sha256 == file_sha256,
        )
    )
    if existing_import is not None and existing_import.status in {
        DominioPayrollImportStatus.COMPLETED.value,
        DominioPayrollImportStatus.COMPLETED_WITH_WARNINGS.value,
        DominioPayrollImportStatus.MANUAL_REVIEW.value,
    }:
        if not dry_run:
            record_audit_event(
                session,
                event_type=IMPORT_DUPLICATE_EVENT,
                message="Dominio payroll import skipped because the same file hash was already imported.",
                actor_type=actor_type,
                actor_id=actor_id,
                resource_type="organization",
                resource_id=str(organization.id),
                event_metadata=_build_audit_metadata_from_import(existing_import, duplicate=True),
            )
            session.commit()
        return _result_from_import(
            existing_import,
            duplicate=True,
            already_processing=False,
            dry_run=dry_run,
        )
    if existing_import is not None and existing_import.status == DominioPayrollImportStatus.PROCESSING.value:
        return _result_from_import(existing_import, duplicate=False, already_processing=True, dry_run=dry_run)

    started_at = datetime.now(timezone.utc)
    if dry_run:
        _, prepared = _parse_and_prepare(
            session,
            organization=organization,
            file_path=normalized_path,
            parser_callable=parser_callable,
        )
        return DominioPayrollImportResult(
            import_id=None,
            duplicate=False,
            already_processing=False,
            dry_run=True,
            status="DRY_RUN",
            selection_scope=manifest_metadata.selection_scope,
            source_filter_name=manifest_metadata.source_filter_name,
            target_company_count=manifest_metadata.target_company_count,
            target_list_sha256=manifest_metadata.target_list_sha256,
            file_sha256=file_sha256,
            physical_page_count=prepared.report.physical_page_count,
            total_companies=prepared.total_companies,
            total_matched=prepared.total_matched,
            total_unmatched=prepared.total_unmatched,
            total_invalid_cnpj=prepared.total_invalid_cnpj,
            total_missing_cnpj=prepared.total_missing_cnpj,
            total_ambiguous=prepared.total_ambiguous,
            total_warnings=prepared.total_warnings,
            total_errors=prepared.total_errors,
            source_competences=prepared.source_competences,
            assessment_competences=prepared.assessment_competences,
        )

    sync_run = IntegrationSyncRun(
        organization_id=organization.id,
        integration_account_id=None,
        provider=DOMINIO_PAYROLL_SYNC_PROVIDER,
        job_name=DOMINIO_PAYROLL_SYNC_JOB,
        status="RUNNING",
        started_at=started_at,
        summary={},
        run_metadata={
            "file_sha256": file_sha256,
            "dry_run": False,
        },
    )

    if existing_import is None:
        payroll_import = DominioPayrollImport(
            organization_id=organization.id,
            source="DOMINIO_FOLHA_RESUMO",
            evidence_source="DOMINIO_FOLHA_PDF",
            parser_version="pending",
            status=DominioPayrollImportStatus.PROCESSING.value,
            selection_scope=manifest_metadata.selection_scope,
            source_filter_name=manifest_metadata.source_filter_name,
            target_company_count=manifest_metadata.target_company_count,
            target_list_sha256=manifest_metadata.target_list_sha256,
            source_file_name=_sanitize_file_name(normalized_path.name),
            source_file_path=_normalize_internal_path(normalized_path),
            file_sha256=file_sha256,
            file_size_bytes=file_size_bytes,
            physical_page_count=0,
            source_competences=[],
            assessment_competences=[],
            started_at=started_at,
            warnings=[],
            errors=[],
            raw_metadata={"duplicate": False},
        )
        session.add(payroll_import)
    else:
        payroll_import = existing_import
        payroll_import.status = DominioPayrollImportStatus.PROCESSING.value
        payroll_import.selection_scope = manifest_metadata.selection_scope
        payroll_import.source_filter_name = manifest_metadata.source_filter_name
        payroll_import.target_company_count = manifest_metadata.target_company_count
        payroll_import.target_list_sha256 = manifest_metadata.target_list_sha256
        payroll_import.source_file_name = _sanitize_file_name(normalized_path.name)
        payroll_import.source_file_path = _normalize_internal_path(normalized_path)
        payroll_import.file_size_bytes = file_size_bytes
        payroll_import.physical_page_count = 0
        payroll_import.source_competences = []
        payroll_import.assessment_competences = []
        payroll_import.assessment_period_id = None
        payroll_import.started_at = started_at
        payroll_import.processed_at = None
        payroll_import.imported_at = None
        payroll_import.total_companies = 0
        payroll_import.total_matched = 0
        payroll_import.total_unmatched = 0
        payroll_import.total_invalid_cnpj = 0
        payroll_import.total_missing_cnpj = 0
        payroll_import.total_ambiguous = 0
        payroll_import.total_warnings = 0
        payroll_import.total_errors = 0
        payroll_import.warnings = []
        payroll_import.errors = []
        payroll_import.raw_metadata = {"duplicate": False, "retry": True}

    session.add(sync_run)
    session.flush()
    session.commit()

    try:
        record_audit_event(
            session,
            event_type=IMPORT_STARTED_EVENT,
            message="Dominio payroll import started.",
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type="dominio_payroll_import",
            resource_id=str(payroll_import.id),
            event_metadata={"file_sha256": file_sha256},
        )
        session.commit()

        report, prepared = _parse_and_prepare(
            session,
            organization=organization,
            file_path=normalized_path,
            parser_callable=parser_callable,
        )

        _delete_previous_retry_state(session, organization_id=organization.id, import_id=payroll_import.id, file_sha256=file_sha256)

        assessment_period_id = _resolve_single_assessment_period_id(
            session,
            organization=organization,
            assessment_competences=prepared.assessment_competences,
        )

        matched = 0
        unmatched = 0
        invalid_cnpj = 0
        missing_cnpj = 0
        ambiguous = 0

        for company in report.companies:
            match = match_dominio_company_by_cnpj(
                session,
                organization=organization,
                company_cnpj=company.company_cnpj,
                company_cnpj_status=company.company_cnpj_status,
            )
            if match.match_status == DominioPayrollMatchStatus.MATCHED.value:
                matched += 1
            elif match.match_status == DominioPayrollMatchStatus.UNMATCHED.value:
                unmatched += 1
            elif match.match_status == DominioPayrollMatchStatus.INVALID_CNPJ.value:
                invalid_cnpj += 1
            elif match.match_status == DominioPayrollMatchStatus.MISSING_CNPJ.value:
                missing_cnpj += 1
            elif match.match_status == DominioPayrollMatchStatus.AMBIGUOUS.value:
                ambiguous += 1

            movement_period_id = _get_or_create_period_id(
                session,
                organization=organization,
                competence=company.assessment_competence,
            )
            movement = DominioPayrollCompanyMovement(
                import_id=payroll_import.id,
                organization_id=organization.id,
                external_company_id=match.external_company_id,
                fiscal_period_id=movement_period_id,
                source_company_key=company.company_key,
                dominio_company_code=company.dominio_company_code,
                company_cnpj=company.company_cnpj,
                source_company_name=company.company_name,
                source_payroll_competence=_competence_to_month_date(company.source_payroll_competence),
                assessment_competence=_competence_to_month_date(company.assessment_competence),
                match_status=match.match_status,
                parser_confidence=company.confidence.value,
                calculation_type=company.calculation_type,
                has_payroll=company.has_payroll,
                has_employee=company.has_employee,
                has_pro_labore=company.has_pro_labore,
                has_autonomous=company.has_autonomous,
                has_inss=company.has_inss,
                has_fgts=company.has_fgts,
                has_termination=company.has_termination,
                has_vacation=company.has_vacation,
                has_leave=company.has_leave,
                gross_total=company.gross_total,
                discount_total=company.discount_total,
                informative_total=company.informative_total,
                net_total=company.net_total,
                source_page_start=min(company.physical_page_numbers) if company.physical_page_numbers else None,
                source_page_end=max(company.physical_page_numbers) if company.physical_page_numbers else None,
                source_page_count=len(company.physical_page_numbers),
                source_page_numbers=list(company.physical_page_numbers),
                declared_page_count=company.declared_page_count,
                movement_hash=_compute_movement_hash(company),
                rubrics_summary=_build_rubrics_summary(company),
                warnings=_sanitize_warnings(company.warnings),
                raw_text=company.raw_text,
            )
            session.add(movement)
            session.flush()

            if match.match_status != DominioPayrollMatchStatus.MATCHED.value:
                continue

            session.add(
                FiscalEvidence(
                    organization_id=organization.id,
                    company_id=match.external_company_id,
                    period_id=movement_period_id,
                    source="DOMINIO_FOLHA_PDF",
                    source_type="DOMINIO_PAYROLL_IMPORT",
                    file_path=payroll_import.source_file_path,
                    file_hash=file_sha256,
                    file_name=payroll_import.source_file_name,
                    detected_tax="PREVIDENCIA_FOLHA",
                    detected_obligation="DOMINIO_FOLHA",
                    cnpj_detected=company.company_cnpj,
                    razao_social_detected=None,
                    competencia_detected=company.assessment_competence,
                    amount_total=company.net_total,
                    confidence=_confidence_to_numeric(company.confidence.value),
                    raw_text=None,
                    raw_payload={
                        "dominio_payroll_import_id": payroll_import.id,
                        "dominio_payroll_movement_id": movement.id,
                        "source_payroll_competence": company.source_payroll_competence,
                        "assessment_competence": company.assessment_competence,
                        "file_sha256": file_sha256,
                        "parser_version": report.parser_version,
                        "signals": _movement_signals(company),
                    },
                    status="PENDENTE",
                )
            )

        payroll_import.source = report.source.value
        payroll_import.evidence_source = report.evidence_source.value
        payroll_import.parser_version = report.parser_version
        payroll_import.status = _resolve_final_import_status(
            report=report,
            total_unmatched=unmatched,
            total_invalid_cnpj=invalid_cnpj,
            total_missing_cnpj=missing_cnpj,
            total_ambiguous=ambiguous,
            force_manual_review=bool(prepared.scope_warnings),
        )
        payroll_import.physical_page_count = report.physical_page_count
        payroll_import.source_competences = prepared.source_competences
        payroll_import.assessment_competences = prepared.assessment_competences
        payroll_import.assessment_period_id = assessment_period_id
        payroll_import.processed_at = datetime.now(timezone.utc)
        payroll_import.imported_at = payroll_import.processed_at
        payroll_import.total_companies = prepared.total_companies
        payroll_import.total_matched = matched
        payroll_import.total_unmatched = unmatched
        payroll_import.total_invalid_cnpj = invalid_cnpj
        payroll_import.total_missing_cnpj = missing_cnpj
        payroll_import.total_ambiguous = ambiguous
        payroll_import.total_warnings = prepared.total_warnings
        payroll_import.total_errors = 0
        payroll_import.warnings = _sanitize_warnings(report.warnings) + prepared.scope_warnings
        payroll_import.errors = []
        payroll_import.raw_metadata = {
            "physical_page_count": report.physical_page_count,
            "total_movements": len(report.companies),
            "elapsed_seconds": round(perf_counter() - started_timer, 6),
            "manifest": _manifest_metadata_payload(manifest_metadata),
            "parsed_distinct_company_count": prepared.total_companies,
        }

        sync_run.status = _sync_run_status_from_import_status(payroll_import.status)
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.processed_count = prepared.total_companies
        sync_run.created_count = prepared.total_companies + matched
        sync_run.updated_count = 0
        sync_run.error_count = 0
        sync_run.errors = None
        sync_run.summary = _build_run_summary(payroll_import)
        sync_run.run_metadata = {
            "file_sha256": file_sha256,
            "physical_page_count": report.physical_page_count,
            "source_competences": prepared.source_competences,
            "assessment_competences": prepared.assessment_competences,
            "dry_run": False,
            "selection_scope": payroll_import.selection_scope,
            "source_filter_name": payroll_import.source_filter_name,
            "target_company_count": payroll_import.target_company_count,
            "target_list_sha256": payroll_import.target_list_sha256,
        }

        record_audit_event(
            session,
            event_type=IMPORT_COMPLETED_EVENT,
            message="Dominio payroll import completed.",
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type="dominio_payroll_import",
            resource_id=str(payroll_import.id),
            event_metadata=_build_audit_metadata_from_import(payroll_import, duplicate=False),
        )
        session.commit()
        return _result_from_import(payroll_import, duplicate=False, already_processing=False, dry_run=False)
    except IntegrityError:
        session.rollback()
        if existing_import is None:
            concurrent_import = session.scalar(
                select(DominioPayrollImport).where(
                    DominioPayrollImport.organization_id == organization.id,
                    DominioPayrollImport.file_sha256 == file_sha256,
                )
            )
            if concurrent_import is not None:
                return _result_from_import(concurrent_import, duplicate=False, already_processing=True, dry_run=False)
        raise
    except Exception as exc:
        session.rollback()
        _mark_import_failed(
            session,
            payroll_import_id=payroll_import.id,
            sync_run_id=sync_run.id,
            actor_type=actor_type,
            actor_id=actor_id,
            organization_id=organization.id,
            file_sha256=file_sha256,
            error=exc,
        )
        raise


def _parse_and_prepare(
    session: Session,
    *,
    organization: Organization,
    file_path: Path,
    parser_callable: Callable[[Path], DominioPayrollReport],
) -> tuple[DominioPayrollReport, _PreparedImportData]:
    report = parser_callable(file_path)
    manifest_metadata = _load_manifest_selection_metadata(file_path)
    matched = 0
    unmatched = 0
    invalid_cnpj = 0
    missing_cnpj = 0
    ambiguous = 0
    for company in report.companies:
        match = match_dominio_company_by_cnpj(
            session,
            organization=organization,
            company_cnpj=company.company_cnpj,
            company_cnpj_status=company.company_cnpj_status,
        )
        if match.match_status == DominioPayrollMatchStatus.MATCHED.value:
            matched += 1
        elif match.match_status == DominioPayrollMatchStatus.UNMATCHED.value:
            unmatched += 1
        elif match.match_status == DominioPayrollMatchStatus.INVALID_CNPJ.value:
            invalid_cnpj += 1
        elif match.match_status == DominioPayrollMatchStatus.MISSING_CNPJ.value:
            missing_cnpj += 1
        elif match.match_status == DominioPayrollMatchStatus.AMBIGUOUS.value:
            ambiguous += 1
    scope_warnings = _build_scope_warnings(
        manifest_metadata=manifest_metadata,
        parsed_distinct_company_count=len(report.companies),
    )
    prepared = _PreparedImportData(
        report=report,
        total_companies=len(report.companies),
        total_matched=matched,
        total_unmatched=unmatched,
        total_invalid_cnpj=invalid_cnpj,
        total_missing_cnpj=missing_cnpj,
        total_ambiguous=ambiguous,
        total_warnings=len(report.warnings) + sum(len(company.warnings) for company in report.companies) + len(scope_warnings),
        total_errors=0,
        scope_warnings=scope_warnings,
        source_competences=list(report.detected_source_competences),
        assessment_competences=list(report.detected_assessment_competences),
    )
    return report, prepared


def _delete_previous_retry_state(session: Session, *, organization_id: int, import_id: int, file_sha256: str) -> None:
    session.execute(
        delete(FiscalEvidence).where(
            FiscalEvidence.organization_id == organization_id,
            FiscalEvidence.source == "DOMINIO_FOLHA_PDF",
            FiscalEvidence.file_hash == file_sha256,
        )
    )
    session.execute(delete(DominioPayrollCompanyMovement).where(DominioPayrollCompanyMovement.import_id == import_id))


def _resolve_single_assessment_period_id(
    session: Session,
    *,
    organization: Organization,
    assessment_competences: list[str],
) -> int | None:
    if len(assessment_competences) != 1:
        return None
    return _get_or_create_period_id(session, organization=organization, competence=assessment_competences[0])


def _get_or_create_period_id(session: Session, *, organization: Organization, competence: str | None) -> int | None:
    if competence is None:
        return None
    month_date = _competence_to_month_date(competence)
    if month_date is None:
        return None
    year = month_date.year
    month = month_date.month
    period = session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.organization_id == organization.id,
            FiscalPeriod.competencia == competence,
        )
    )
    if period is not None:
        return period.id
    period = FiscalPeriod(
        organization_id=organization.id,
        year=year,
        month=month,
        competencia=competence,
        status="OPEN",
    )
    session.add(period)
    session.flush()
    return period.id


def _build_rubrics_summary(company: DominioPayrollCompany) -> dict[str, Any]:
    codes = sorted({rubric.code for rubric in company.rubrics if rubric.code})
    unknown_codes = sorted({rubric.code for rubric in company.rubrics if not rubric.code})
    return {
        "schema_version": DOMINIO_PAYROLL_RUBRICS_SCHEMA_VERSION,
        "rubric_count": len(company.rubrics),
        "codes": codes,
        "unknown_codes": unknown_codes,
        "signals": {
            evidence.signal: {
                "value": evidence.value,
                "rubric_codes": sorted(evidence.rubric_codes),
            }
            for evidence in sorted(company.signal_sources, key=lambda item: item.signal)
        },
        "blocks": [
            {
                "block_type": block.block_type.value,
                "description": block.description,
                "rubric_count": len(block.rubrics),
                "gross_total": _decimal_to_string(_sum_declared_total(block, "EARNINGS")),
                "discount_total": _decimal_to_string(_sum_declared_total(block, "DEDUCTIONS")),
                "informative_total": _decimal_to_string(_sum_declared_total(block, "INFORMATIONAL")),
            }
            for block in company.blocks
        ],
    }


def _sum_declared_total(block, section_name: str) -> Decimal | None:
    value = block.declared_totals.get(section_name)
    if value is not None:
        return value
    values = [section.declared_total for section in block.sections if section.section_type.value == section_name and section.declared_total is not None]
    if not values:
        return None
    return sum(values, Decimal("0.00")).quantize(Decimal("0.01"))


def _compute_movement_hash(company: DominioPayrollCompany) -> str:
    payload = {
        "company_key": company.company_key,
        "source_payroll_competence": company.source_payroll_competence,
        "assessment_competence": company.assessment_competence,
        "parser_confidence": company.confidence.value,
        "signals": _movement_signals(company),
        "totals": {
            "gross_total": _decimal_to_string(company.gross_total),
            "discount_total": _decimal_to_string(company.discount_total),
            "informative_total": _decimal_to_string(company.informative_total),
            "net_total": _decimal_to_string(company.net_total),
        },
        "pages": list(company.physical_page_numbers),
        "rubrics_summary": _build_rubrics_summary(company),
        "warnings": [warning.code.value for warning in company.warnings],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _movement_signals(company: DominioPayrollCompany) -> dict[str, bool]:
    return {
        "has_payroll": company.has_payroll,
        "has_employee": company.has_employee,
        "has_pro_labore": company.has_pro_labore,
        "has_autonomous": company.has_autonomous,
        "has_inss": company.has_inss,
        "has_fgts": company.has_fgts,
        "has_termination": company.has_termination,
        "has_vacation": company.has_vacation,
        "has_leave": company.has_leave,
    }


def _sanitize_warnings(warnings) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for warning in warnings:
        context = warning.context or None
        sanitized.append(
            {
                "code": warning.code.value,
                "message": warning.message,
                "physical_page_number": warning.physical_page_number,
                "context": context,
            }
        )
    return sanitized


def _resolve_final_import_status(
    *,
    report: DominioPayrollReport,
    total_unmatched: int,
    total_invalid_cnpj: int,
    total_missing_cnpj: int,
    total_ambiguous: int,
    force_manual_review: bool = False,
) -> str:
    if force_manual_review:
        return DominioPayrollImportStatus.MANUAL_REVIEW.value
    if total_unmatched or total_invalid_cnpj or total_missing_cnpj or total_ambiguous:
        return DominioPayrollImportStatus.MANUAL_REVIEW.value
    if any(company.confidence.value == "LOW" for company in report.companies):
        return DominioPayrollImportStatus.MANUAL_REVIEW.value
    warning_codes = {warning.code.value for warning in report.warnings}
    warning_codes.update(warning.code.value for company in report.companies for warning in company.warnings)
    if warning_codes.intersection(RELEVANT_WARNING_CODES):
        return DominioPayrollImportStatus.COMPLETED_WITH_WARNINGS.value
    return DominioPayrollImportStatus.COMPLETED.value


def _sync_run_status_from_import_status(import_status: str) -> str:
    if import_status == DominioPayrollImportStatus.COMPLETED.value:
        return "SUCCESS"
    if import_status in {
        DominioPayrollImportStatus.COMPLETED_WITH_WARNINGS.value,
        DominioPayrollImportStatus.MANUAL_REVIEW.value,
    }:
        return "PARTIAL"
    return "FAILED"


def _mark_import_failed(
    session: Session,
    *,
    payroll_import_id: int,
    sync_run_id: int,
    actor_type: str | None,
    actor_id: str | None,
    organization_id: int,
    file_sha256: str,
    error: Exception,
) -> None:
    sanitized_error = _sanitize_error(error)
    payroll_import = session.get(DominioPayrollImport, payroll_import_id)
    if payroll_import is not None:
        payroll_import.status = DominioPayrollImportStatus.FAILED.value
        payroll_import.processed_at = datetime.now(timezone.utc)
        payroll_import.imported_at = None
        payroll_import.total_errors = 1
        payroll_import.errors = [sanitized_error]
    sync_run = session.get(IntegrationSyncRun, sync_run_id)
    if sync_run is not None:
        sync_run.status = "FAILED"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.error_count = 1
        sync_run.errors = [sanitized_error]
        sync_run.summary = {"file_sha256": file_sha256, "status": "FAILED"}
    record_audit_event(
        session,
        event_type=IMPORT_FAILED_EVENT,
        message="Dominio payroll import failed.",
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type="organization",
        resource_id=str(organization_id),
        event_metadata={"file_sha256": file_sha256, "error": sanitized_error["code"]},
    )
    session.commit()


def _sanitize_error(error: Exception) -> dict[str, str]:
    return {
        "code": error.__class__.__name__.upper(),
        "message": str(error).splitlines()[0][:255],
    }


def _build_run_summary(payroll_import: DominioPayrollImport) -> dict[str, Any]:
    return {
        "file_sha256": payroll_import.file_sha256,
        "physical_page_count": payroll_import.physical_page_count,
        "selection_scope": payroll_import.selection_scope,
        "source_filter_name": payroll_import.source_filter_name,
        "target_company_count": payroll_import.target_company_count,
        "target_list_sha256": payroll_import.target_list_sha256,
        "source_competences": payroll_import.source_competences,
        "assessment_competences": payroll_import.assessment_competences,
        "total_companies": payroll_import.total_companies,
        "total_matched": payroll_import.total_matched,
        "total_unmatched": payroll_import.total_unmatched,
        "total_invalid_cnpj": payroll_import.total_invalid_cnpj,
        "total_missing_cnpj": payroll_import.total_missing_cnpj,
        "total_ambiguous": payroll_import.total_ambiguous,
        "total_warnings": payroll_import.total_warnings,
        "status": payroll_import.status,
    }


def _result_from_import(
    payroll_import: DominioPayrollImport,
    *,
    duplicate: bool,
    already_processing: bool,
    dry_run: bool,
) -> DominioPayrollImportResult:
    return DominioPayrollImportResult(
        import_id=payroll_import.id,
        duplicate=duplicate,
        already_processing=already_processing,
        dry_run=dry_run,
        status=payroll_import.status,
        selection_scope=payroll_import.selection_scope,
        source_filter_name=payroll_import.source_filter_name,
        target_company_count=payroll_import.target_company_count,
        target_list_sha256=payroll_import.target_list_sha256,
        file_sha256=payroll_import.file_sha256,
        physical_page_count=payroll_import.physical_page_count,
        total_companies=payroll_import.total_companies,
        total_matched=payroll_import.total_matched,
        total_unmatched=payroll_import.total_unmatched,
        total_invalid_cnpj=payroll_import.total_invalid_cnpj,
        total_missing_cnpj=payroll_import.total_missing_cnpj,
        total_ambiguous=payroll_import.total_ambiguous,
        total_warnings=payroll_import.total_warnings,
        total_errors=payroll_import.total_errors,
        source_competences=list(payroll_import.source_competences),
        assessment_competences=list(payroll_import.assessment_competences),
    )


def _build_audit_metadata_from_import(payroll_import: DominioPayrollImport, *, duplicate: bool) -> dict[str, Any]:
    return {
        "duplicate": duplicate,
        "file_sha256": payroll_import.file_sha256,
        "status": payroll_import.status,
        "selection_scope": payroll_import.selection_scope,
        "source_filter_name": payroll_import.source_filter_name,
        "target_company_count": payroll_import.target_company_count,
        "target_list_sha256": payroll_import.target_list_sha256,
        "physical_page_count": payroll_import.physical_page_count,
        "source_competences": payroll_import.source_competences,
        "assessment_competences": payroll_import.assessment_competences,
        "total_companies": payroll_import.total_companies,
        "total_matched": payroll_import.total_matched,
        "total_unmatched": payroll_import.total_unmatched,
        "total_invalid_cnpj": payroll_import.total_invalid_cnpj,
        "total_missing_cnpj": payroll_import.total_missing_cnpj,
        "total_ambiguous": payroll_import.total_ambiguous,
        "total_warnings": payroll_import.total_warnings,
        "total_errors": payroll_import.total_errors,
    }


def _compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest_selection_metadata(file_path: Path) -> DominioManifestSelectionMetadata:
    manifest_path = file_path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        return build_manifest_selection_metadata(
            selection_scope=None,
            source_filter_name=None,
            target_company_count=None,
            target_list_sha256=None,
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Dominio manifest sidecar: {manifest_path}") from exc
    return build_manifest_selection_metadata(
        selection_scope=payload.get("selection_scope"),
        source_filter_name=payload.get("source_filter_name"),
        target_company_count=payload.get("target_company_count"),
        target_list_sha256=payload.get("target_list_sha256"),
    )


def _manifest_metadata_payload(metadata: DominioManifestSelectionMetadata) -> dict[str, Any]:
    return {
        "selection_scope": metadata.selection_scope,
        "source_filter_name": metadata.source_filter_name,
        "target_company_count": metadata.target_company_count,
        "target_list_sha256": metadata.target_list_sha256,
        "original_selection_scope": metadata.original_selection_scope,
    }


def _build_scope_warnings(
    *,
    manifest_metadata: DominioManifestSelectionMetadata,
    parsed_distinct_company_count: int,
) -> list[dict[str, Any]]:
    if manifest_metadata.selection_scope != "FACTOR_R":
        return []
    target_company_count = manifest_metadata.target_company_count
    if target_company_count is None:
        return []
    if target_company_count == 0 and parsed_distinct_company_count > 0:
        return [
            {
                "code": FACTOR_R_TARGET_SCOPE_MISMATCH,
                "message": "Factor R target scope metadata is inconsistent with the parsed company count.",
                "context": {
                    "target_company_count": target_company_count,
                    "parsed_distinct_company_count": parsed_distinct_company_count,
                },
            }
        ]
    if parsed_distinct_company_count > target_company_count:
        return [
            {
                "code": FACTOR_R_TARGET_SCOPE_MISMATCH,
                "message": "Factor R target scope metadata is inconsistent with the parsed company count.",
                "context": {
                    "target_company_count": target_company_count,
                    "parsed_distinct_company_count": parsed_distinct_company_count,
                },
            }
        ]
    return []


def _sanitize_file_name(file_name: str) -> str:
    sanitized = SAFE_FILE_NAME_RE.sub("_", Path(file_name).name).strip("._")
    return sanitized or "dominio_payroll.pdf"


def _normalize_internal_path(path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return None


def _competence_to_month_date(value: str | None) -> date | None:
    if value is None:
        return None
    year_text, month_text = value.split("-", maxsplit=1)
    return date(int(year_text), int(month_text), 1)


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.01")), "f")


def _confidence_to_numeric(value: str) -> Decimal:
    mapping = {
        "HIGH": Decimal("100.00"),
        "MEDIUM": Decimal("70.00"),
        "LOW": Decimal("40.00"),
    }
    return mapping.get(value, Decimal("0.00"))
