from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio import watcher
from backend.app.services.integrations.dominio.importer import DominioPayrollImportResult


def _manifest(pdf: Path) -> Path:
    manifest = pdf.with_suffix(".manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "status": "SUCCESS",
                "selection_scope": "ACTIVE_COMPANIES",
                "pdf_file_name": pdf.name,
                "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "pdf_size_bytes": pdf.stat().st_size,
                "pdf_page_count": 1,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_valid_manifest_requires_canonical_name_hash_size_and_pages(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "Resumo_Mensal_07-2026.pdf"
    pdf.write_bytes(b"synthetic")
    manifest = _manifest(pdf)
    monkeypatch.setattr(watcher, "PdfReader", lambda _: type("Reader", (), {"pages": [object()]})())

    assert watcher._valid_manifest(pdf, manifest) is not None

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["selection_scope"] = "ALL_COMPANIES"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert watcher._valid_manifest(pdf, manifest) is None


def test_partial_or_invalid_reports_are_not_imported(tmp_path: Path, db_session, monkeypatch) -> None:
    partial = tmp_path / "Resumo_Mensal_07-2026.partial.pdf"
    partial.write_bytes(b"partial")
    invalid = tmp_path / "Resumo_Mensal_08-2026.pdf"
    invalid.write_bytes(b"invalid")
    called = []
    monkeypatch.setattr(watcher, "import_dominio_payroll_file", lambda *args, **kwargs: called.append(args))
    organization = Organization(name="Watcher", slug="watcher")
    db_session.add(organization)
    db_session.flush()

    result = watcher.run_dominio_payroll_watcher_once(
        db_session, organization=organization, directory=tmp_path, dry_run=True
    )

    assert result.scanned == 2
    assert result.invalid == 1
    assert result.partial == 1
    assert called == []


def test_new_report_imports_and_reconciles_only_its_assessment_period(tmp_path: Path, db_session, monkeypatch) -> None:
    pdf = tmp_path / "Resumo_Mensal_07-2026.pdf"
    pdf.write_bytes(b"synthetic")
    organization = Organization(name="Watcher trigger", slug="watcher-trigger")
    db_session.add(organization)
    db_session.flush()
    periods: list[str] = []
    result = DominioPayrollImportResult(
        import_id=1, duplicate=False, already_processing=False, dry_run=False, status="COMPLETED",
        selection_scope="ACTIVE_COMPANIES", source_filter_name="Ativas", target_company_count=None,
        target_list_sha256=None, file_sha256="a" * 64, physical_page_count=1, total_companies=1,
        total_matched=1, total_unmatched=0, total_invalid_cnpj=0, total_missing_cnpj=0,
        total_ambiguous=0, total_warnings=0, total_errors=0, source_competences=["2026-07"],
        assessment_competences=["2026-08"],
    )
    monkeypatch.setattr(watcher, "_valid_manifest", lambda *_: {"pdf_sha256": "a" * 64})
    monkeypatch.setattr(watcher, "import_dominio_payroll_file", lambda *args, **kwargs: result)
    monkeypatch.setattr(watcher, "reconcile_dctfweb_period", lambda _db, _org, period, **kwargs: periods.append(f"dctf:{period}"))
    monkeypatch.setattr(watcher, "reconcile_factor_r_period", lambda _db, _org, period, **kwargs: periods.append(f"factor:{period}"))

    summary = watcher.run_dominio_payroll_watcher_once(
        db_session, organization=organization, directory=tmp_path
    )

    assert summary.imported == 1
    assert summary.dctfweb_reconciled == 1
    assert summary.factor_r_reconciled == 1
    assert periods == ["dctf:2026-08", "factor:2026-08"]
