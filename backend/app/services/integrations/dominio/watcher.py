from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.dominio_payroll import DominioPayrollImport
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.dctfweb_origins import reconcile_dctfweb_period
from backend.app.services.factor_r_reconciliation import reconcile_factor_r_period
from backend.app.services.integrations.dominio.importer import import_dominio_payroll_file


WATCHER_PROVIDER = "WATCHER_DOMINIO"
WATCHER_JOB = "watch_dominio_payroll_reports"
REPORT_NAME_RE = re.compile(r"^Resumo_Mensal_(0[1-9]|1[0-2])-(\d{4})\.pdf$")


@dataclass(frozen=True, slots=True)
class DominioWatcherSummary:
    dry_run: bool
    scanned: int = 0
    valid: int = 0
    invalid: int = 0
    partial: int = 0
    already_imported: int = 0
    imported: int = 0
    failed: int = 0
    dctfweb_reconciled: int = 0
    factor_r_reconciled: int = 0

    def to_dict(self) -> dict[str, int | bool]:
        return {
            "dry_run": self.dry_run,
            "scanned": self.scanned,
            "valid": self.valid,
            "invalid": self.invalid,
            "partial": self.partial,
            "already_imported": self.already_imported,
            "imported": self.imported,
            "failed": self.failed,
            "dctfweb_reconciled": self.dctfweb_reconciled,
            "factor_r_reconciled": self.factor_r_reconciled,
        }


def run_dominio_payroll_watcher_once(
    session: Session,
    *,
    organization: Organization,
    directory: str | Path,
    dry_run: bool = False,
) -> DominioWatcherSummary:
    directory_path = Path(directory)
    if not directory_path.is_dir():
        raise FileNotFoundError("Domínio watcher directory was not found.")

    counters = {key: 0 for key in DominioWatcherSummary(dry_run=dry_run).to_dict() if key != "dry_run"}
    started_at = datetime.now(timezone.utc)
    run = None
    if not dry_run:
        run = IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider=WATCHER_PROVIDER,
            job_name=WATCHER_JOB,
            status="RUNNING",
            started_at=started_at,
            summary={},
            run_metadata={},
        )
        session.add(run)
        session.commit()

    detected_at = None
    imported_at = None
    try:
        for pdf_path in sorted(directory_path.glob("Resumo_Mensal_*.pdf")):
            counters["scanned"] += 1
            if pdf_path.name.endswith(".partial.pdf"):
                counters["partial"] += 1
                continue
            manifest_path = pdf_path.with_suffix(".manifest.json")
            manifest = _valid_manifest(pdf_path, manifest_path)
            if manifest is None:
                counters["invalid"] += 1
                continue
            counters["valid"] += 1
            detected_at = datetime.now(timezone.utc).isoformat()
            file_hash = str(manifest["pdf_sha256"])
            existing = session.scalar(select(DominioPayrollImport).where(
                DominioPayrollImport.organization_id == organization.id,
                DominioPayrollImport.file_sha256 == file_hash,
            ))
            if existing is not None:
                counters["already_imported"] += 1
                continue

            result = import_dominio_payroll_file(
                session,
                organization=organization,
                file_path=pdf_path,
                dry_run=dry_run,
                actor_id="dominio-payroll-watcher",
            )
            if result.dry_run:
                counters["imported"] += 1
                continue
            if result.status == "FAILED":
                counters["failed"] += 1
                continue
            counters["imported"] += 1
            imported_at = datetime.now(timezone.utc).isoformat()
            for period in result.assessment_competences:
                reconcile_dctfweb_period(session, organization, period, dry_run=False)
                counters["dctfweb_reconciled"] += 1
                # Factor R is only recalculated for the payroll report's M+1 assessment period.
                reconcile_factor_r_period(session, organization, period, dry_run=False)
                counters["factor_r_reconciled"] += 1
    except Exception:
        counters["failed"] += 1
        raise
    finally:
        if run is not None:
            summary = DominioWatcherSummary(dry_run=False, **counters)
            run.status = "FAILED" if counters["failed"] else "SUCCESS"
            run.finished_at = datetime.now(timezone.utc)
            run.processed_count = counters["valid"]
            run.created_count = counters["imported"]
            run.updated_count = counters["dctfweb_reconciled"] + counters["factor_r_reconciled"]
            run.error_count = counters["failed"] + counters["invalid"]
            run.summary = summary.to_dict()
            run.run_metadata = {"detected_at": detected_at, "imported_at": imported_at}
            session.commit()

    return DominioWatcherSummary(dry_run=dry_run, **counters)


def _valid_manifest(pdf_path: Path, manifest_path: Path) -> dict[str, object] | None:
    if REPORT_NAME_RE.fullmatch(pdf_path.name) is None or not manifest_path.is_file():
        return None
    before = pdf_path.stat()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        page_count = len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return None
    after = pdf_path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        return None
    required = (
        manifest.get("status") == "SUCCESS",
        manifest.get("selection_scope") == "ACTIVE_COMPANIES",
        manifest.get("pdf_file_name") == pdf_path.name,
        manifest.get("pdf_sha256") == digest,
        manifest.get("pdf_size_bytes") == before.st_size,
        manifest.get("pdf_page_count") == page_count and page_count > 0,
    )
    return manifest if all(required) else None
