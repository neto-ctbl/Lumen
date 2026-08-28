from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.models.dctfweb_origin import DctfwebOriginAssessment
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.factor_r_assessment import FactorRAssessment
from backend.app.models.audit_log import AuditLog
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.services.auth import ROLE_ADMIN, ROLE_VIEW
from test_lumen_read_endpoints import login_headers, seed_auth_context, seed_company, seed_period


pytest_plugins = ("test_lumen_read_endpoints",)


def _seed_dominio_import(db_session, *, organization_id: int, period: FiscalPeriod) -> DominioPayrollImport:
    payroll_import = DominioPayrollImport(
        organization_id=organization_id,
        assessment_period_id=period.id,
        source="DOMINIO",
        evidence_source="DOMINIO_PAYROLL",
        parser_version="test",
        status="COMPLETED_WITH_WARNINGS",
        selection_scope="ACTIVE_COMPANIES",
        source_filter_name="Ativas",
        source_file_name="synthetic.pdf",
        source_file_path="C:/sensitive/synthetic.pdf",
        file_sha256="a" * 64,
        file_size_bytes=1,
        physical_page_count=1,
        source_competences=["2026-07"],
        assessment_competences=["2026-08"],
        total_companies=2,
        total_matched=1,
        total_unmatched=1,
        total_invalid_cnpj=0,
        total_missing_cnpj=0,
        total_ambiguous=0,
        total_warnings=3,
        total_errors=0,
        warnings=[],
        errors=[],
    )
    db_session.add(payroll_import)
    db_session.flush()
    return payroll_import


def _seed_movement(db_session, *, payroll_import: DominioPayrollImport, company_id: int, period: FiscalPeriod) -> None:
    db_session.add(
        DominioPayrollCompanyMovement(
            import_id=payroll_import.id,
            organization_id=payroll_import.organization_id,
            external_company_id=company_id,
            fiscal_period_id=period.id,
            source_company_key="synthetic-company",
            dominio_company_code="1",
            company_cnpj="11111111000111",
            source_company_name="Sensitive source name",
            source_payroll_competence=date(2026, 7, 1),
            assessment_competence=date(2026, 8, 1),
            match_status="MATCHED",
            parser_confidence="HIGH",
            has_payroll=True,
            has_employee=True,
            has_pro_labore=False,
            has_autonomous=False,
            has_inss=True,
            has_fgts=True,
            has_termination=False,
            has_vacation=False,
            has_leave=False,
            source_page_count=1,
            source_page_numbers=[1],
            movement_hash="b" * 64,
            rubrics_summary={
                "schema_version": 2,
                "monetary_summary_confidence": "PARTIAL",
                "monetary_categories": {
                    "employee_remuneration": {"amount": "1234.56"},
                    "pro_labore": {"amount": "0.00"},
                    "autonomous": {"amount": "0.00"},
                    "thirteenth_salary": {"amount": "0.00"},
                    "employer_cpp_observed": {"amount": "0.00"},
                    "fgts_observed": {"amount": "0.00"},
                },
                "unclassified_monetary": {"amount": "500.00", "rubric_count": 1},
            },
            warnings=[{"code": "UNCLASSIFIED_MONETARY_RUBRICS"}],
            raw_text="NEVER EXPOSE RAW PAYROLL",
        )
    )
    db_session.flush()


def _seed_dctfweb(db_session, *, organization_id: int, company_id: int, period: FiscalPeriod) -> None:
    db_session.add(
        DctfwebOriginAssessment(
            organization_id=organization_id,
            external_company_id=company_id,
            fiscal_period_id=period.id,
            assessment_competence=date(2026, 7, 1),
            source_payroll_competence=date(2026, 6, 1),
            dp_coverage_status="CONFIRMED_MOVEMENT",
            dp_signal_present=True,
            reinf_signal_present=True,
            mit_signal_present=False,
            fiscal_signal_present=True,
            dctfweb_observed=False,
            expected_origin="COMPARTILHADO",
            expected_responsible_department="COMPARTILHADO",
            classification_confidence="HIGH",
            reason_codes=["DCTFWEB_SHARED_ORIGIN_DETECTED"],
            source_summary={"internal": "do not expose"},
            fingerprint="c" * 64,
            evaluated_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()


def _seed_factor_r(db_session, *, organization_id: int, company_id: int, period: FiscalPeriod) -> None:
    db_session.add(
        FactorRAssessment(
            organization_id=organization_id,
            external_company_id=company_id,
            fiscal_period_id=period.id,
            applicability_status="EFFECTIVE",
            calculation_status="COMPUTED",
            payroll_window_start=date(2025, 7, 1),
            payroll_window_end=date(2026, 6, 1),
            payroll_months_expected=12,
            payroll_months_covered=12,
            payroll_months_with_movement=4,
            payroll_months_confirmed_zero=8,
            payroll_months_missing=0,
            fs12_dominio_estimate=Decimal("28000.00"),
            fs12_confidence="LOW",
            fs12_breakdown={"employee_remuneration": "28000.00", "total_estimated": "28000.00"},
            rbt12_value=Decimal("100000.00"),
            rbt12_source="SITTAX",
            rbt12_confidence="OBSERVED",
            factor_r_estimated_dominio=Decimal("0.279999"),
            estimated_threshold_side="BELOW_28",
            estimated_annex="V",
            factor_r_sittax_observed=Decimal("0.275000"),
            sittax_observed_annexes=[],
            factor_r_delta=Decimal("0.004999"),
            reconciliation_status="THRESHOLD_DIVERGENCE",
            reason_codes=["CASH_BASIS_UNVERIFIED", "THIRTEENTH_SALARY_COVERAGE_UNVERIFIED"],
            source_summary={"raw": "do not expose"},
            fingerprint="d" * 64,
            evaluated_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()


def test_s95_read_endpoints_are_sanitized_and_cover_dominio_states(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="s95-read")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    no_movement = seed_company(db_session, organization_id=organization.id, cnpj="22222222000122", razao_social="Beta Ltda")
    period_08 = seed_period(db_session, organization_id=organization.id, competencia="2026-08")
    period_07 = seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    payroll_import = _seed_dominio_import(db_session, organization_id=organization.id, period=period_08)
    _seed_movement(db_session, payroll_import=payroll_import, company_id=company.id, period=period_08)
    _seed_dctfweb(db_session, organization_id=organization.id, company_id=company.id, period=period_07)
    _seed_factor_r(db_session, organization_id=organization.id, company_id=company.id, period=period_07)
    headers = login_headers(client, email=user.email, password=password)

    summary = client.get("/api/v1/lumen/dominio/payroll/summary?sourcePeriod=2026-07", headers=headers)
    detail = client.get(f"/api/v1/lumen/companies/{company.id}/dominio/payroll?sourcePeriod=2026-07", headers=headers)
    zero = client.get(f"/api/v1/lumen/companies/{no_movement.id}/dominio/payroll?sourcePeriod=2026-07", headers=headers)
    missing = client.get(f"/api/v1/lumen/companies/{company.id}/dominio/payroll?sourcePeriod=2025-01", headers=headers)

    assert summary.status_code == 200
    assert summary.json()["schema_v2_movements"] == 1
    assert detail.status_code == 200
    assert detail.json()["coverage_status"] == "MOVEMENT_FOUND"
    assert detail.json()["monetary_summary"]["employee_remuneration"] == "1234.56"
    assert "raw_text" not in detail.text and "file_sha256" not in detail.text and "Sensitive source name" not in detail.text
    assert zero.json()["coverage_status"] == "CONFIRMED_NO_MOVEMENT"
    assert missing.json()["coverage_status"] == "REPORT_MISSING"

    dctfweb = client.get("/api/v1/lumen/dctfweb/origins?period=2026-07", headers=headers)
    factor = client.get("/api/v1/lumen/factor-r?period=2026-07", headers=headers)
    factor_detail = client.get(f"/api/v1/lumen/companies/{company.id}/factor-r?period=2026-07", headers=headers)
    assert dctfweb.status_code == 200 and dctfweb.json()["items"][0]["expected_origin"] == "COMPARTILHADO"
    assert factor.status_code == 200 and factor.json()["items"][0]["factor_r_estimated"] == "0.279999"
    assert factor_detail.status_code == 200 and "source_summary" not in factor_detail.text and "fingerprint" not in factor_detail.text


def test_s95_dashboard_cockpit_and_company_summary_are_enriched(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="s95-enriched")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    period = seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    _seed_dctfweb(db_session, organization_id=organization.id, company_id=company.id, period=period)
    _seed_factor_r(db_session, organization_id=organization.id, company_id=company.id, period=period)
    headers = login_headers(client, email=user.email, password=password)

    dashboard = client.get("/api/v1/lumen/dashboard?period=2026-07", headers=headers)
    cockpit = client.get("/api/v1/lumen/cockpit?period=2026-07", headers=headers)
    company_summary = client.get(f"/api/v1/lumen/companies/{company.id}/summary?period=2026-07", headers=headers)

    assert dashboard.json()["dctfweb"]["shared"] == 1
    assert dashboard.json()["factor_r"]["threshold_divergences"] == 1
    assert cockpit.json()["items"][0]["dctfweb_origin"] == "COMPARTILHADO"
    assert cockpit.json()["items"][0]["factor_r_reconciliation_status"] == "THRESHOLD_DIVERGENCE"
    assert company_summary.json()["regime_label"] == "Aguardando Acessorias"
    assert company_summary.json()["factor_r_confidence"] == "LOW"
    assert company_summary.json()["dominio_source_period"] == "2026-06"


def test_s95_isolates_tenants_and_requires_admin_for_reconcile(client: TestClient, db_session) -> None:
    view_user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="s95-view")
    _, other_org, _ = seed_auth_context(db_session, role=ROLE_ADMIN, slug="s95-other")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    other_company = seed_company(db_session, organization_id=other_org.id, cnpj="22222222000122", razao_social="Beta Ltda")
    period = seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    _seed_factor_r(db_session, organization_id=organization.id, company_id=company.id, period=period)
    headers = login_headers(client, email=view_user.email, password=password)

    other = client.get(f"/api/v1/lumen/companies/{other_company.id}/factor-r?period=2026-07", headers=headers)
    blocked = client.post("/api/v1/lumen/factor-r/reconcile", headers=headers, json={"period": "2026-07", "dry_run": True})

    assert other.status_code == 404
    assert blocked.status_code == 403


def test_s95_reconcile_dry_run_has_zero_writes(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_ADMIN, slug="s95-admin")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    headers = login_headers(client, email=user.email, password=password)
    before = (
        db_session.scalar(select(func.count()).select_from(DctfwebOriginAssessment)) or 0,
        db_session.scalar(select(func.count()).select_from(FactorRAssessment)) or 0,
        db_session.scalar(select(func.count()).select_from(FiscalAlert)) or 0,
    )

    dctfweb = client.post("/api/v1/lumen/dctfweb/reconcile", headers=headers, json={"period": "2026-07", "company_id": company.id, "dry_run": True})
    factor = client.post("/api/v1/lumen/factor-r/reconcile", headers=headers, json={"period": "2026-07", "company_id": company.id, "dry_run": True})
    after = (
        db_session.scalar(select(func.count()).select_from(DctfwebOriginAssessment)) or 0,
        db_session.scalar(select(func.count()).select_from(FactorRAssessment)) or 0,
        db_session.scalar(select(func.count()).select_from(FiscalAlert)) or 0,
    )

    assert dctfweb.status_code == 200
    assert factor.status_code == 200
    assert before == after


def test_s95_reconcile_real_writes_only_local_assessments(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_ADMIN, slug="s95-real")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    headers = login_headers(client, email=user.email, password=password)

    dctfweb = client.post("/api/v1/lumen/dctfweb/reconcile", headers=headers, json={"period": "2026-07", "company_id": company.id})
    factor = client.post("/api/v1/lumen/factor-r/reconcile", headers=headers, json={"period": "2026-07", "company_id": company.id})

    assert dctfweb.status_code == 200
    assert factor.status_code == 200
    assert db_session.scalar(select(func.count()).select_from(DctfwebOriginAssessment)) == 1
    assert db_session.scalar(select(func.count()).select_from(FactorRAssessment)) == 1


def test_s95_get_requests_have_zero_writes(client: TestClient, db_session) -> None:
    user, organization, password = seed_auth_context(db_session, role=ROLE_VIEW, slug="s95-zero-writes")
    company = seed_company(db_session, organization_id=organization.id, cnpj="11111111000111", razao_social="Alpha Ltda")
    period = seed_period(db_session, organization_id=organization.id, competencia="2026-07")
    _seed_dctfweb(db_session, organization_id=organization.id, company_id=company.id, period=period)
    _seed_factor_r(db_session, organization_id=organization.id, company_id=company.id, period=period)
    headers = login_headers(client, email=user.email, password=password)
    before = tuple(
        db_session.scalar(select(func.count()).select_from(model)) or 0
        for model in (DctfwebOriginAssessment, FactorRAssessment, FiscalAlert, AuditLog)
    )

    responses = [
        client.get("/api/v1/lumen/dashboard?period=2026-07", headers=headers),
        client.get("/api/v1/lumen/cockpit?period=2026-07", headers=headers),
        client.get("/api/v1/lumen/dctfweb/summary?period=2026-07", headers=headers),
        client.get("/api/v1/lumen/factor-r/summary?period=2026-07", headers=headers),
        client.get("/api/v1/lumen/integrations/health", headers=headers),
    ]
    after = tuple(
        db_session.scalar(select(func.count()).select_from(model)) or 0
        for model in (DctfwebOriginAssessment, FactorRAssessment, FiscalAlert, AuditLog)
    )

    assert all(response.status_code == 200 for response in responses)
    assert before == after
