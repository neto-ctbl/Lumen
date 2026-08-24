from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from sqlalchemy import select

from backend.app.models.audit_log import AuditLog
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement
from backend.app.services.integrations.dominio.contracts import DominioCnpjStatus
from backend.app.services.integrations.dominio.enrichment import enrich_dominio_payroll_monetary_summary
from backend.app.services.integrations.dominio.importer import import_dominio_payroll_file
from backend.tests.test_dominio_payroll_importer import _create_company, _create_org, _make_company, _make_report, _write_fake_pdf


def test_enrichment_updates_only_rubrics_summary_and_is_idempotent(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-enrichment")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    report = _make_report(
        _make_company(
            company_code="0001",
            company_name="Empresa A",
            company_cnpj="12345678000195",
            cnpj_status=DominioCnpjStatus.VALID,
        )
    )

    import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: report,
    )

    movement = db_session.scalar(select(DominioPayrollCompanyMovement))
    assert movement is not None
    original_snapshot = {
        "import_id": movement.import_id,
        "organization_id": movement.organization_id,
        "external_company_id": movement.external_company_id,
        "fiscal_period_id": movement.fiscal_period_id,
        "source_company_key": movement.source_company_key,
        "match_status": movement.match_status,
        "movement_hash": movement.movement_hash,
        "warnings": deepcopy(movement.warnings),
        "raw_text": movement.raw_text,
    }

    movement.rubrics_summary = {"schema_version": 1, "codes": ["1"]}
    db_session.commit()

    dry_run = enrich_dominio_payroll_monetary_summary(
        db_session,
        organization=organization,
        file_path=file_path,
        dry_run=True,
        parser_callable=lambda path: report,
    )
    db_session.refresh(movement)

    assert dry_run.movements_changed == 1
    assert movement.rubrics_summary == {"schema_version": 1, "codes": ["1"]}

    first = enrich_dominio_payroll_monetary_summary(
        db_session,
        organization=organization,
        file_path=file_path,
        dry_run=False,
        parser_callable=lambda path: report,
    )
    db_session.refresh(movement)

    assert first.movements_changed == 1
    assert movement.rubrics_summary["schema_version"] == 2
    assert movement.rubrics_summary["monetary_categories"]["employee_remuneration"]["amount"] == "3615.81"
    assert movement.import_id == original_snapshot["import_id"]
    assert movement.organization_id == original_snapshot["organization_id"]
    assert movement.external_company_id == original_snapshot["external_company_id"]
    assert movement.fiscal_period_id == original_snapshot["fiscal_period_id"]
    assert movement.source_company_key == original_snapshot["source_company_key"]
    assert movement.match_status == original_snapshot["match_status"]
    assert movement.movement_hash == original_snapshot["movement_hash"]
    assert movement.warnings == original_snapshot["warnings"]
    assert movement.raw_text == original_snapshot["raw_text"]

    second = enrich_dominio_payroll_monetary_summary(
        db_session,
        organization=organization,
        file_path=file_path,
        dry_run=False,
        parser_callable=lambda path: report,
    )

    assert second.movements_changed == 0
    assert second.already_enriched == 1
    audit_events = db_session.scalars(
        select(AuditLog).where(AuditLog.event_type == "DOMINIO_PAYROLL_MONETARY_ENRICHMENT").order_by(AuditLog.id.asc())
    ).all()
    assert [event.event_metadata["movements_updated"] for event in audit_events] == [1, 0]
    assert "Empresa A" not in json.dumps([event.event_metadata for event in audit_events], sort_keys=True)


def test_enrichment_aborts_on_source_company_key_mismatch(db_session, tmp_path: Path) -> None:
    organization = _create_org(db_session, "org-dominio-enrichment-mismatch")
    _create_company(db_session, organization, cnpj="12345678000195")
    file_path = _write_fake_pdf(tmp_path)
    imported_report = _make_report(
        _make_company(
            company_code="0001",
            company_name="Empresa A",
            company_cnpj="12345678000195",
            cnpj_status=DominioCnpjStatus.VALID,
        )
    )
    mismatch_report = _make_report(
        _make_company(
            company_code="9999",
            company_name="Empresa A",
            company_cnpj="12345678000195",
            cnpj_status=DominioCnpjStatus.VALID,
        )
    )

    import_dominio_payroll_file(
        db_session,
        organization=organization,
        file_path=file_path,
        parser_callable=lambda path: imported_report,
    )

    movement = db_session.scalar(select(DominioPayrollCompanyMovement))
    assert movement is not None
    original_summary = deepcopy(movement.rubrics_summary)

    try:
        enrich_dominio_payroll_monetary_summary(
            db_session,
            organization=organization,
            file_path=file_path,
            dry_run=False,
            parser_callable=lambda path: mismatch_report,
        )
    except ValueError as exc:
        assert "mismatch" in str(exc).lower()
    else:
        raise AssertionError("Expected the enrichment to abort on source_company_key mismatch.")

    db_session.refresh(movement)
    assert movement.rubrics_summary == original_summary
