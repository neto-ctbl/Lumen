from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from backend.app.models import ExternalCompany, FiscalEvidence, FiscalObligation, FiscalObligationStatus, FiscalPeriod, Organization
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.acessorias_delivery_snapshot import AcessoriasDeliverySnapshot
from backend.app.models.audit_log import AuditLog
from backend.app.models.dctfweb_origin import DctfwebOriginAssessment
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.services.dctfweb_origins import (
    DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED,
    DCTFWEB_ORIGIN_UNDETERMINED,
    DCTFWEB_SHARED_ORIGIN_DETECTED,
    DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
    reconcile_dctfweb_period,
)


def _organization(session, slug: str = "dctfweb-org") -> Organization:
    row = Organization(name=slug, slug=slug)
    session.add(row)
    session.flush()
    return row


def _company(session, organization: Organization, suffix: str = "90", *, active: bool = True) -> ExternalCompany:
    row = ExternalCompany(
        organization_id=organization.id,
        cnpj=f"123456780001{suffix}",
        razao_social="Empresa Sintetica",
        active=active,
    )
    session.add(row)
    session.flush()
    return row


def _period(session, organization: Organization, competence: str = "2026-07") -> FiscalPeriod:
    row = FiscalPeriod(
        organization_id=organization.id,
        year=int(competence[:4]),
        month=int(competence[5:]),
        competencia=competence,
        status="OPEN",
    )
    session.add(row)
    session.flush()
    return row


def _import(session, organization: Organization, period: FiscalPeriod, scope: str = "ACTIVE_COMPANIES") -> DominioPayrollImport:
    file_hash = hashlib.sha256(f"{organization.slug}:{period.competencia}:{scope}".encode()).hexdigest()
    row = DominioPayrollImport(
        organization_id=organization.id,
        assessment_period_id=period.id,
        source="DOMINIO",
        evidence_source="DOMINIO_FOLHA_PDF",
        parser_version="test",
        status="COMPLETED",
        selection_scope=scope,
        source_filter_name="Ativas" if scope == "ACTIVE_COMPANIES" else "Fator R",
        source_file_name="synthetic.pdf",
        source_file_path=None,
        file_sha256=file_hash,
        file_size_bytes=1,
        physical_page_count=1,
        source_competences=["2026-06"],
        assessment_competences=[period.competencia],
        total_companies=1,
        total_matched=1,
        total_unmatched=0,
        total_invalid_cnpj=0,
        total_missing_cnpj=0,
        total_ambiguous=0,
        total_warnings=0,
        total_errors=0,
        warnings=[],
        errors=[],
    )
    session.add(row)
    session.flush()
    return row


def _movement(
    session,
    organization: Organization,
    company: ExternalCompany,
    period: FiscalPeriod,
    payroll_import: DominioPayrollImport,
    **signals: bool,
) -> DominioPayrollCompanyMovement:
    defaults = {
        "has_payroll": False,
        "has_employee": False,
        "has_pro_labore": False,
        "has_autonomous": False,
        "has_inss": False,
        "has_fgts": False,
        "has_termination": False,
        "has_vacation": False,
        "has_leave": False,
    }
    defaults.update(signals)
    row = DominioPayrollCompanyMovement(
        import_id=payroll_import.id,
        organization_id=organization.id,
        external_company_id=company.id,
        fiscal_period_id=period.id,
        source_company_key=f"company-{company.id}",
        dominio_company_code="1",
        company_cnpj=company.cnpj,
        source_company_name="Empresa Sintetica",
        source_payroll_competence=date(2026, 6, 1),
        assessment_competence=date(period.year, period.month, 1),
        match_status="MATCHED",
        parser_confidence="HIGH",
        calculation_type="Folha Mensal",
        source_page_count=1,
        source_page_numbers=[1],
        movement_hash=f"{company.id:064d}",
        rubrics_summary={},
        warnings=[],
        raw_text="synthetic",
        **defaults,
    )
    session.add(row)
    session.flush()
    return row


def _obligation(session, code: str) -> FiscalObligation:
    row = FiscalObligation(code=code, name=code, category="FEDERAL", department_default="FISCAL", source_priority=[])
    session.add(row)
    session.flush()
    return row


def _status(session, organization: Organization, company: ExternalCompany, period: FiscalPeriod, obligation: FiscalObligation) -> None:
    session.add(
        FiscalObligationStatus(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            obligation_id=obligation.id,
            status="PENDENTE",
            responsible_department="FISCAL",
        )
    )
    session.flush()


def _assess(session, organization: Organization, competence: str = "2026-07", **kwargs):
    return reconcile_dctfweb_period(
        session,
        organization,
        competence,
        now=datetime(2026, 8, 20, tzinfo=timezone.utc),
        **kwargs,
    )


def test_dp_coverage_distinguishes_movement_no_movement_and_missing_report(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    with_movement = _company(db_session, organization, "90")
    no_movement = _company(db_session, organization, "91")
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, with_movement, period, payroll_import, has_pro_labore=True)

    _assess(db_session, organization)

    rows = {row.external_company_id: row for row in db_session.scalars(select(DctfwebOriginAssessment)).all()}
    assert rows[with_movement.id].dp_coverage_status == "CONFIRMED_MOVEMENT"
    assert rows[with_movement.id].expected_origin == "DP"
    assert rows[no_movement.id].dp_coverage_status == "CONFIRMED_NO_MOVEMENT"
    assert rows[no_movement.id].expected_origin == "UNDETERMINED"
    assert rows[no_movement.id].expected_responsible_department is None
    assert rows[no_movement.id].reason_codes == ["NO_DCTFWEB_COMPONENT_OBSERVED"]

    missing_org = _organization(db_session, "dctfweb-missing")
    _period(db_session, missing_org)
    _company(db_session, missing_org)
    _assess(db_session, missing_org)
    missing = db_session.scalar(
        select(DctfwebOriginAssessment).where(DctfwebOriginAssessment.organization_id == missing_org.id)
    )
    assert missing is not None and missing.dp_coverage_status == "REPORT_MISSING"
    alert = db_session.scalar(
        select(FiscalAlert).where(
            FiscalAlert.organization_id == missing_org.id,
            FiscalAlert.code == DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
        )
    )
    assert alert is not None
    assert alert.company_id is None


def test_factor_r_import_is_not_canonical_dominio_coverage(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    factor_r_import = _import(db_session, organization, period, scope="FACTOR_R")
    _movement(db_session, organization, company, period, factor_r_import, has_pro_labore=True)

    _assess(db_session, organization)

    assessment = db_session.scalar(select(DctfwebOriginAssessment))
    assert assessment is not None
    assert assessment.dp_coverage_status == "REPORT_MISSING"
    assert assessment.dp_signal_present is False


def test_origin_rules_cover_dp_fiscal_shared_and_undetermined(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    dp_company = _company(db_session, organization, "90")
    shared_company = _company(db_session, organization, "91")
    fiscal_company = _company(db_session, organization, "92")
    import_row = _import(db_session, organization, period)
    _movement(db_session, organization, dp_company, period, import_row, has_pro_labore=True)
    _movement(db_session, organization, shared_company, period, import_row, has_autonomous=True)
    reinf = _obligation(db_session, "REINF")
    dctfweb = _obligation(db_session, "DCTFWEB")
    _status(db_session, organization, shared_company, period, reinf)
    _status(db_session, organization, fiscal_company, period, reinf)
    _status(db_session, organization, dp_company, period, dctfweb)

    _assess(db_session, organization)

    rows = {row.external_company_id: row for row in db_session.scalars(select(DctfwebOriginAssessment)).all()}
    assert rows[dp_company.id].expected_origin == "DP"
    assert rows[shared_company.id].expected_origin == "COMPARTILHADO"
    assert rows[fiscal_company.id].expected_origin == "FISCAL"
    assert rows[shared_company.id].reinf_signal_present is True
    assert rows[shared_company.id].mit_signal_present is False
    assert rows[dp_company.id].dctfweb_observed is True
    assert db_session.scalar(select(FiscalObligationStatus).where(FiscalObligationStatus.company_id == shared_company.id)).status == "PENDENTE"


def test_fgts_alone_is_not_dp_and_observed_dctfweb_is_undetermined(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, company, period, payroll_import, has_fgts=True)
    _status(db_session, organization, company, period, _obligation(db_session, "DCTFWEB"))

    _assess(db_session, organization)

    assessment = db_session.scalar(select(DctfwebOriginAssessment))
    assert assessment is not None
    assert assessment.expected_origin == "UNDETERMINED"
    assert "DCTFWEB_WITHOUT_ORIGIN_SIGNAL" in assessment.reason_codes
    assert db_session.scalar(select(FiscalAlert).where(FiscalAlert.code == DCTFWEB_ORIGIN_UNDETERMINED))


def test_assessment_and_alerts_are_idempotent_and_shared_alert_resolves(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, company, period, payroll_import, has_employee=True)
    reinf = _obligation(db_session, "REINF")
    fiscal_status = FiscalObligationStatus(
        organization_id=organization.id,
        company_id=company.id,
        period_id=period.id,
        obligation_id=reinf.id,
        status="PENDENTE",
        responsible_department="FISCAL",
    )
    db_session.add(fiscal_status)
    db_session.flush()

    _assess(db_session, organization)
    first = db_session.scalar(select(DctfwebOriginAssessment))
    assert first is not None
    fingerprint = first.fingerprint
    _assess(db_session, organization)
    assert len(db_session.scalars(select(DctfwebOriginAssessment)).all()) == 1
    assert db_session.scalar(select(DctfwebOriginAssessment)).fingerprint == fingerprint
    assert len(db_session.scalars(select(FiscalAlert).where(FiscalAlert.code == DCTFWEB_SHARED_ORIGIN_DETECTED)).all()) == 1

    db_session.delete(fiscal_status)
    db_session.flush()
    _assess(db_session, organization)
    assessment = db_session.scalar(select(DctfwebOriginAssessment))
    assert assessment is not None
    assert assessment.expected_origin == "DP"
    shared_alert = db_session.scalar(select(FiscalAlert).where(FiscalAlert.code == DCTFWEB_SHARED_ORIGIN_DETECTED))
    assert shared_alert is not None and shared_alert.status == "RESOLVED"
    assert assessment.fingerprint != fingerprint


def test_dry_run_does_not_persist_assessments_or_alerts(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, company, period, payroll_import, has_autonomous=True)

    before = {
        "assessments": db_session.scalar(select(func.count(DctfwebOriginAssessment.id))),
        "alerts": db_session.scalar(select(func.count(FiscalAlert.id))),
        "audit_log": db_session.scalar(select(func.count(AuditLog.id))),
        "statuses": db_session.scalar(select(func.count(FiscalObligationStatus.id))),
        "evidences": db_session.scalar(select(func.count(FiscalEvidence.id))),
        "periods": db_session.scalar(select(func.count(FiscalPeriod.id))),
    }

    summary = _assess(db_session, organization, dry_run=True)

    assert summary.companies_evaluated == 1
    assert db_session.scalars(select(DctfwebOriginAssessment)).all() == []
    assert db_session.scalars(select(FiscalAlert)).all() == []
    assert before == {
        "assessments": db_session.scalar(select(func.count(DctfwebOriginAssessment.id))),
        "alerts": db_session.scalar(select(func.count(FiscalAlert.id))),
        "audit_log": db_session.scalar(select(func.count(AuditLog.id))),
        "statuses": db_session.scalar(select(func.count(FiscalObligationStatus.id))),
        "evidences": db_session.scalar(select(func.count(FiscalEvidence.id))),
        "periods": db_session.scalar(select(func.count(FiscalPeriod.id))),
    }


def test_multi_tenant_evidence_isolated(db_session) -> None:
    first_org = _organization(db_session, "dctfweb-org-a")
    second_org = _organization(db_session, "dctfweb-org-b")
    first_period = _period(db_session, first_org)
    second_period = _period(db_session, second_org)
    first_company = _company(db_session, first_org, "90")
    second_company = _company(db_session, second_org, "90")
    first_import = _import(db_session, first_org, first_period)
    _movement(db_session, first_org, first_company, first_period, first_import, has_employee=True)
    second_reinf = _obligation(db_session, "REINF")
    _status(db_session, second_org, second_company, second_period, second_reinf)

    _assess(db_session, first_org)
    _assess(db_session, second_org)

    first = db_session.scalar(select(DctfwebOriginAssessment).where(DctfwebOriginAssessment.organization_id == first_org.id))
    second = db_session.scalar(select(DctfwebOriginAssessment).where(DctfwebOriginAssessment.organization_id == second_org.id))
    assert first is not None and first.expected_origin == "DP"
    assert second is not None and second.expected_origin == "UNDETERMINED"


def test_reinf_evidence_is_a_fiscal_signal(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    _import(db_session, organization, period)
    db_session.add(
        FiscalEvidence(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            source="TEST",
            source_type="TEST",
            detected_obligation="REINF",
            status="PENDENTE",
        )
    )
    db_session.flush()

    _assess(db_session, organization)

    assessment = db_session.scalar(select(DctfwebOriginAssessment))
    assert assessment is not None
    assert assessment.expected_origin == "FISCAL"
    assert assessment.dp_coverage_status == "CONFIRMED_NO_MOVEMENT"
    assert assessment.reinf_signal_present is True
    assert assessment.mit_signal_present is False


def test_acessorias_dctfweb_delivery_observes_without_deciding_origin(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    _import(db_session, organization, period)
    dctfweb = _obligation(db_session, "DCTFWEB")
    db_session.add(
        AcessoriasDeliverySnapshot(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            external_company_id="synthetic-company",
            identifier=company.cnpj,
            external_delivery_id="synthetic-delivery",
            obligation_name="DCTFWeb",
            obligation_id=dctfweb.id,
            obligation_mapping_status="MAPPED",
            normalized_status="PENDENTE",
            retrieved_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
    )
    db_session.flush()

    summary = _assess(db_session, organization)

    assessment = db_session.scalar(select(DctfwebOriginAssessment))
    assert assessment is not None
    assert assessment.dctfweb_observed is True
    assert assessment.expected_origin == "UNDETERMINED"
    assert summary.dctfweb_observed == 1


def test_active_universe_assesses_companies_without_signals_and_excludes_inactive(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    dp_company = _company(db_session, organization, "90")
    no_signal_company = _company(db_session, organization, "91")
    inactive_company = _company(db_session, organization, "92", active=False)
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, dp_company, period, payroll_import, has_employee=True)

    summary = _assess(db_session, organization)

    rows = {row.external_company_id: row for row in db_session.scalars(select(DctfwebOriginAssessment)).all()}
    assert set(rows) == {dp_company.id, no_signal_company.id}
    assert inactive_company.id not in rows
    assert rows[no_signal_company.id].expected_origin == "UNDETERMINED"
    assert rows[no_signal_company.id].expected_responsible_department is None
    assert rows[no_signal_company.id].reason_codes == ["NO_DCTFWEB_COMPONENT_OBSERVED"]
    assert summary.companies_evaluated == 2
    assert summary.dp + summary.fiscal + summary.shared + summary.undetermined == summary.companies_evaluated


def test_mit_uses_only_canonical_pis_cofins_from_2025_onward(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization, "2025-01")
    pis_company = _company(db_session, organization, "90")
    cofins_company = _company(db_session, organization, "91")
    das_company = _company(db_session, organization, "92")
    before_company = _company(db_session, organization, "93")
    regime_only_company = _company(db_session, organization, "94")
    before_period = _period(db_session, organization, "2024-12")
    _import(db_session, organization, period)
    _import(db_session, organization, before_period)
    pis = _obligation(db_session, "PIS")
    _obligation(db_session, "COFINS")
    das = _obligation(db_session, "DAS")
    _status(db_session, organization, pis_company, period, pis)
    _status(db_session, organization, das_company, period, das)
    _status(db_session, organization, before_company, before_period, pis)
    db_session.add(
        FiscalEvidence(
            organization_id=organization.id,
            company_id=cofins_company.id,
            period_id=period.id,
            source="TEST",
            source_type="TEST",
            detected_obligation="COFINS",
            status="PENDENTE",
        )
    )
    db_session.add(
        AcessoriasCompanySnapshot(
            organization_id=organization.id,
            company_id=regime_only_company.id,
            external_company_id="synthetic-regime-only",
            identifier=regime_only_company.cnpj,
            razao_social="Empresa Sintetica",
            regime_canonical="SIMPLES_NACIONAL",
            regime_mapping_status="MAPPED",
            retrieved_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
    )
    db_session.flush()

    january_summary = _assess(db_session, organization, "2025-01")
    december_summary = _assess(db_session, organization, "2024-12")

    january_rows = {
        row.external_company_id: row
        for row in db_session.scalars(
            select(DctfwebOriginAssessment).where(DctfwebOriginAssessment.fiscal_period_id == period.id)
        ).all()
    }
    december = db_session.scalar(
        select(DctfwebOriginAssessment).where(
            DctfwebOriginAssessment.external_company_id == before_company.id,
            DctfwebOriginAssessment.fiscal_period_id == before_period.id,
        )
    )
    assert january_rows[pis_company.id].mit_signal_present is True
    assert january_rows[pis_company.id].fiscal_signal_present is True
    assert "MIT_PIS_COFINS_SIGNAL" in january_rows[pis_company.id].reason_codes
    assert january_rows[cofins_company.id].mit_signal_present is True
    assert january_rows[das_company.id].mit_signal_present is False
    assert january_rows[das_company.id].expected_origin == "UNDETERMINED"
    assert january_rows[regime_only_company.id].mit_signal_present is False
    assert december is not None and december.mit_signal_present is False
    assert january_summary.mit_signal_companies == 2
    assert december_summary.mit_signal_companies == 0


def test_monthly_dominio_report_alert_is_singleton_per_org_period(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    first_company = _company(db_session, organization, "90")
    second_company = _company(db_session, organization, "91")
    db_session.add(
        FiscalAlert(
            organization_id=organization.id,
            company_id=first_company.id,
            period_id=period.id,
            obligation_status_id=None,
            code=DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
            title="old",
            message="old",
            severity="LOW",
            department="SISTEMA",
            source="LUMEN_DCTFWEB_RECONCILIATION",
            status="OPEN",
            rule_key=DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
            details={},
        )
    )
    db_session.flush()

    _assess(db_session, organization)

    alerts = db_session.scalars(
        select(FiscalAlert)
        .where(
            FiscalAlert.organization_id == organization.id,
            FiscalAlert.period_id == period.id,
            FiscalAlert.code == DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
        )
        .order_by(FiscalAlert.id)
    ).all()
    open_singletons = [alert for alert in alerts if alert.company_id is None and alert.status == "OPEN"]
    company_alerts = [alert for alert in alerts if alert.company_id in {first_company.id, second_company.id}]
    assert len(open_singletons) == 1
    assert all(alert.status == "RESOLVED" for alert in company_alerts)


def test_next_month_review_alert_is_created_for_prior_dp_period(db_session) -> None:
    organization = _organization(db_session)
    period = _period(db_session, organization)
    company = _company(db_session, organization)
    payroll_import = _import(db_session, organization, period)
    _movement(db_session, organization, company, period, payroll_import, has_employee=True)

    _assess(db_session, organization)

    _period(db_session, organization, "2026-08")
    _assess(db_session, organization, "2026-08")

    alert = db_session.scalar(
        select(FiscalAlert).where(
            FiscalAlert.code == DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED,
            FiscalAlert.period_id != period.id,
        )
    )
    assert alert is not None
