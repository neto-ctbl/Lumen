from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.organization import Organization
from backend.app.services.audit import record_audit_event
from backend.app.services.integrations.dominio.contracts import DominioPayrollReport
from backend.app.services.integrations.dominio.importer import _build_rubrics_summary
from backend.app.services.integrations.dominio.parser import parse_dominio_payroll_pdf


MONETARY_ENRICHMENT_EVENT = "DOMINIO_PAYROLL_MONETARY_ENRICHMENT"


@dataclass(frozen=True, slots=True)
class DominioPayrollMonetaryEnrichmentResult:
    file_name: str
    file_sha256: str
    imports_found: int
    movements_parsed: int
    movements_matched: int
    movements_changed: int
    schema_v2: int
    complete: int
    partial: int
    insufficient: int
    unclassified_monetary_movements: int
    already_enriched: int
    dry_run: bool

    def to_public_dict(self) -> dict[str, Any]:
        key = "movements_would_update" if self.dry_run else "movements_updated"
        return {
            "file_name": self.file_name,
            "file_sha256": self.file_sha256,
            "imports_found": self.imports_found,
            "movements_parsed": self.movements_parsed,
            "movements_matched": self.movements_matched,
            key: self.movements_changed,
            "schema_v2": self.schema_v2,
            "complete": self.complete,
            "partial": self.partial,
            "insufficient": self.insufficient,
            "unclassified_monetary_movements": self.unclassified_monetary_movements,
            "already_enriched": self.already_enriched,
            "dry_run": self.dry_run,
        }


def enrich_dominio_payroll_monetary_summary(
    session: Session,
    *,
    organization: Organization,
    file_path: str | Path,
    dry_run: bool = False,
    parser_callable: Callable[[Path], DominioPayrollReport] = parse_dominio_payroll_pdf,
    actor_type: str | None = "system",
    actor_id: str | None = "dominio-payroll-monetary-enrichment-cli",
) -> DominioPayrollMonetaryEnrichmentResult:
    normalized_path = Path(file_path)
    if not normalized_path.exists() or not normalized_path.is_file():
        raise FileNotFoundError(f"Payroll file was not found: {normalized_path}")

    file_sha256 = _compute_file_sha256(normalized_path)
    imports = session.scalars(
        select(DominioPayrollImport).where(
            DominioPayrollImport.organization_id == organization.id,
            DominioPayrollImport.file_sha256 == file_sha256,
        )
    ).all()
    if len(imports) != 1:
        raise ValueError(f"Expected exactly one payroll import for hash {file_sha256}, found {len(imports)}.")

    payroll_import = imports[0]
    report = parser_callable(normalized_path)
    parsed_by_key = {}
    for company in report.companies:
        if company.company_key in parsed_by_key:
            raise ValueError("Parsed report contains duplicate source_company_key values.")
        parsed_by_key[company.company_key] = company

    persisted = session.scalars(
        select(DominioPayrollCompanyMovement)
        .where(DominioPayrollCompanyMovement.import_id == payroll_import.id)
        .order_by(DominioPayrollCompanyMovement.id.asc())
    ).all()
    persisted_by_key: dict[str, DominioPayrollCompanyMovement] = {}
    for movement in persisted:
        if movement.source_company_key in persisted_by_key:
            raise ValueError("Persisted import contains duplicate source_company_key values.")
        persisted_by_key[movement.source_company_key] = movement

    if len(parsed_by_key) != len(persisted_by_key):
        raise ValueError(
            f"Parsed movement count {len(parsed_by_key)} does not match persisted movement count {len(persisted_by_key)}."
        )

    parsed_keys = set(parsed_by_key)
    persisted_keys = set(persisted_by_key)
    if parsed_keys != persisted_keys:
        missing = len(parsed_keys - persisted_keys)
        extra = len(persisted_keys - parsed_keys)
        raise ValueError(f"Source movement key mismatch detected: missing={missing} extra={extra}.")

    changed = 0
    schema_v2 = 0
    complete = 0
    partial = 0
    insufficient = 0
    unclassified = 0
    already_enriched = 0

    for company_key, company in parsed_by_key.items():
        movement = persisted_by_key[company_key]
        summary, _warnings = _build_rubrics_summary(company)
        existing_summary = movement.rubrics_summary or {}
        if existing_summary == summary:
            already_enriched += 1
        else:
            changed += 1
            if not dry_run:
                movement.rubrics_summary = summary

        schema_v2 += int(summary.get("schema_version") == 2)
        confidence = summary.get("monetary_summary_confidence")
        if confidence == "COMPLETE":
            complete += 1
        elif confidence == "PARTIAL":
            partial += 1
        else:
            insufficient += 1
        unclassified += int((summary.get("unclassified_monetary") or {}).get("rubric_count", 0) > 0)

    if not dry_run:
        record_audit_event(
            session,
            event_type=MONETARY_ENRICHMENT_EVENT,
            message="Dominio payroll monetary summary enrichment executed.",
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type="dominio_payroll_import",
            resource_id=str(payroll_import.id),
            event_metadata={
                "file_sha256": file_sha256,
                "movements_parsed": len(parsed_by_key),
                "movements_matched": len(parsed_by_key),
                "movements_updated": changed,
                "schema_v2": schema_v2,
                "complete": complete,
                "partial": partial,
                "insufficient": insufficient,
                "unclassified_monetary_movements": unclassified,
            },
        )
        session.commit()

    return DominioPayrollMonetaryEnrichmentResult(
        file_name=normalized_path.name,
        file_sha256=file_sha256,
        imports_found=1,
        movements_parsed=len(parsed_by_key),
        movements_matched=len(parsed_by_key),
        movements_changed=changed,
        schema_v2=schema_v2,
        complete=complete,
        partial=partial,
        insufficient=insufficient,
        unclassified_monetary_movements=unclassified,
        already_enriched=already_enriched,
        dry_run=dry_run,
    )


def _compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
