from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import inspect, select
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.factor_r_assessment import FactorRAssessment
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.services.integrations.econet.parser import CURRENT_ECONET_PARSER_VERSION
from backend.app.services.factor_r_reconciliation import (
    FACTOR_R_THRESHOLD,
    FS12_LOW,
    FS12_MEDIUM,
    PayrollCoverage,
    build_payroll_window,
    calculate_factor_r,
    classify_factor_r_threshold,
    estimate_fs12_from_dominio,
    normalize_sittax_factor_r_percent,
    reconcile_factor_r_period,
)


def _org(session, slug: str) -> Organization:
    row = Organization(name=slug, slug=slug)
    session.add(row)
    session.flush()
    return row


def _period(session, org: Organization, competence: str) -> FiscalPeriod:
    year, month = (int(item) for item in competence.split("-"))
    row = FiscalPeriod(organization_id=org.id, year=year, month=month, competencia=competence, status="OPEN")
    session.add(row)
    session.flush()
    return row


def _company(session, org: Organization, suffix: str = "1") -> ExternalCompany:
    row = ExternalCompany(
        organization_id=org.id,
        cnpj=f"12345678000{suffix}95",
        razao_social=f"Empresa Sintetica {suffix}",
        active=True,
    )
    session.add(row)
    session.flush()
    session.add(
        AcessoriasCompanySnapshot(
            organization_id=org.id,
            company_id=row.id,
            external_company_id=f"access-{row.id}",
            identifier=row.cnpj,
            razao_social=row.razao_social,
            nome_fantasia=None,
            external_status="ATIVA",
            regime_raw="Simples Nacional",
            regime_code=None,
            regime_canonical="SIMPLES_NACIONAL",
            regime_mapping_status="MAPPED",
            raw_payload={},
            retrieved_at=datetime.now(timezone.utc),
        )
    )
    return row


def _summary(*, thirteenth: Decimal = Decimal("0.00"), unclassified_code: str | None = None) -> dict[str, object]:
    categories = {
        "employee_remuneration": {"amount": "2000.00"},
        "pro_labore": {"amount": "0.00"},
        "autonomous": {"amount": "0.00"},
        "thirteenth_salary": {"amount": f"{thirteenth:.2f}"},
        "employer_cpp_observed": {"amount": "300.00"},
        "fgts_observed": {"amount": "100.00"},
    }
    unclassified = {"amount": "0.00", "rubric_count": 0, "rubric_codes": []}
    if unclassified_code:
        unclassified = {"amount": "500.00", "rubric_count": 1, "rubric_codes": [unclassified_code]}
    return {"schema_version": 2, "monetary_categories": categories, "unclassified_monetary": unclassified}


def _make_factor_r_potential(session, company: ExternalCompany) -> None:
    cnae = f"90000{company.id % 10}1"
    session.add(
        CompanyCnae(
            company_id=company.id,
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4:]}",
            is_primary=True,
            source="TEST",
            active=True,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            deactivated_at=None,
        )
    )
    session.add(
        EconetCnaeCache(
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4:]}",
            description="CNAE sintetico Fator R",
            econet_id_cnae=f"test-{cnae}",
            activity_types=["SERVICOS"],
            simples_status="ALLOWED",
            simples_allowed=True,
            simples_annex_default="V",
            simples_annex_conditional="III",
            factor_r_applicable=True,
            factor_r_threshold=Decimal("28.00"),
            mei_status="NOT_ALLOWED",
            mei_allowed=False,
            mei_occupation=None,
            presumed_profit_status="ALLOWED",
            presumed_profit_allowed=True,
            presumed_profit_irpj_rate=None,
            presumed_profit_csll_rate=None,
            actual_profit_status="ALLOWED",
            actual_profit_mandatory=False,
            obligations_general={},
            obligations_simples={},
            obligations_simei={},
            unmapped_obligations=[],
            normalized_payload={},
            parse_status="PARSED",
            parser_version=CURRENT_ECONET_PARSER_VERSION,
            content_hash=f"{cnae}".ljust(64, "0"),
            retrieved_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
    )


def _movement(session, org: Organization, company: ExternalCompany, source_month: date, *, summary: dict[str, object]) -> None:
    payroll_import = DominioPayrollImport(
        organization_id=org.id,
        assessment_period_id=None,
        source="DOMINIO_FOLHA_RESUMO",
        evidence_source="DOMINIO_FOLHA_PDF",
        parser_version="test",
        status="COMPLETED",
        selection_scope="ACTIVE_COMPANIES",
        source_filter_name="Empresas ativas",
        target_company_count=1,
        target_list_sha256="a" * 64,
        source_file_name=f"synthetic-{source_month:%Y-%m}.pdf",
        source_file_path=None,
        file_sha256=f"{source_month:%Y%m}".ljust(64, "0"),
        file_size_bytes=1,
        physical_page_count=1,
        source_competences=[f"{source_month:%Y-%m}"],
        assessment_competences=[],
        started_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        imported_at=datetime.now(timezone.utc),
        warnings=[],
        errors=[],
        raw_metadata={},
    )
    session.add(payroll_import)
    session.flush()
    session.add(
        DominioPayrollCompanyMovement(
            import_id=payroll_import.id,
            organization_id=org.id,
            external_company_id=company.id,
            fiscal_period_id=None,
            source_company_key=f"{company.id}|{source_month:%Y-%m}",
            dominio_company_code="0001",
            company_cnpj=company.cnpj,
            source_company_name=company.razao_social,
            source_payroll_competence=source_month,
            assessment_competence=None,
            match_status="MATCHED",
            parser_confidence="HIGH",
            calculation_type="Folha",
            has_payroll=True,
            has_employee=True,
            has_pro_labore=False,
            has_autonomous=False,
            has_inss=True,
            has_fgts=True,
            has_termination=False,
            has_vacation=False,
            has_leave=False,
            gross_total=Decimal("9999.00"),
            discount_total=Decimal("0.00"),
            informative_total=Decimal("0.00"),
            net_total=Decimal("9999.00"),
            source_page_start=1,
            source_page_end=1,
            source_page_count=1,
            source_page_numbers=[1],
            declared_page_count=1,
            movement_hash=f"{company.id}{source_month:%Y%m}".ljust(64, "0"),
            rubrics_summary=summary,
            warnings=[],
            raw_text="synthetic",
        )
    )


def _report_without_movement(session, org: Organization, source_month: date) -> None:
    session.add(
        DominioPayrollImport(
            organization_id=org.id,
            assessment_period_id=None,
            source="DOMINIO_FOLHA_RESUMO",
            evidence_source="DOMINIO_FOLHA_PDF",
            parser_version="test",
            status="COMPLETED",
            selection_scope="ACTIVE_COMPANIES",
            source_filter_name="Empresas ativas",
            target_company_count=1,
            target_list_sha256="b" * 64,
            source_file_name=f"synthetic-empty-{source_month:%Y-%m}.pdf",
            source_file_path=None,
            file_sha256=(f"empty{source_month:%Y%m}").ljust(64, "0"),
            file_size_bytes=1,
            physical_page_count=1,
            source_competences=[f"{source_month:%Y-%m}"],
            assessment_competences=[],
            started_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            imported_at=datetime.now(timezone.utc),
            warnings=[],
            errors=[],
            raw_metadata={},
        )
    )


def _sittax(session, org: Organization, company: ExternalCompany, period: FiscalPeriod) -> None:
    company_snapshot = SittaxCompanySnapshot(
        organization_id=org.id,
        company_id=company.id,
        sittax_company_id=f"sittax-{company.id}",
        cnpj=company.cnpj,
        legal_name=company.razao_social,
        trade_name=None,
        state_registration=None,
        state=None,
        status="ATIVA",
        homologated=True,
        cash_regime=False,
        match_status="MATCHED",
        raw_payload={},
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    session.add(company_snapshot)
    session.flush()
    session.add(
        SittaxApuracaoSnapshot(
            organization_id=org.id,
            sittax_company_snapshot_id=company_snapshot.id,
            external_company_id=company.id,
            fiscal_period_id=period.id,
            sittax_apuracao_id=f"apur-{company.id}",
            company_cnpj=company.cnpj,
            company_name=company.razao_social,
            period_reference=period.competencia,
            is_transmitted=True,
            transmission_in_progress=False,
            transmission_type="TEST",
            transmitted_at=datetime.now(timezone.utc),
            net_revenue=Decimal("10000.00"),
            product_revenue=Decimal("0.00"),
            service_revenue=Decimal("10000.00"),
            return_revenue=Decimal("0.00"),
            rbt12=Decimal("100000.00"),
            rba=Decimal("10000.00"),
            das_amount=Decimal("1.00"),
            das_xml_amount=Decimal("1.00"),
            factor_r_percent=Decimal("27.00"),
            company_has_payroll=True,
            taxes_icms=False,
            taxes_iss=True,
            taxes_ipi=False,
            taxes_pis_cofins=False,
            companies_apuracao=[],
            annexes=[{"anexo": "ANEXO_III"}, {"anexo": "ANEXO_V"}],
            cfops=[],
            activities=[],
            payrolls=[],
            alerts=[],
            errors=[],
            risks=[],
            raw_payload={},
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
    )


def test_window_formula_and_sittax_percent_normalization() -> None:
    july = build_payroll_window("2026-07")
    august = build_payroll_window("2026-08")
    january = build_payroll_window("2027-01")
    assert (july.start, july.end) == (date(2025, 7, 1), date(2026, 6, 1))
    assert date(2026, 7, 1) not in july.months
    assert (august.start, august.end) == (date(2025, 8, 1), date(2026, 7, 1))
    assert date(2026, 7, 1) in august.months
    assert (january.start, january.end) == (date(2026, 1, 1), date(2026, 12, 1))
    assert calculate_factor_r(Decimal("28000"), Decimal("100000")) == FACTOR_R_THRESHOLD
    assert classify_factor_r_threshold(Decimal("0.28")) == ("ABOVE_OR_EQUAL_28", "III")
    assert classify_factor_r_threshold(Decimal("0.27999")) == ("BELOW_28", "V")
    assert calculate_factor_r(Decimal("0"), Decimal("0")) == Decimal("0.01")
    assert calculate_factor_r(Decimal("1"), Decimal("0")) == FACTOR_R_THRESHOLD
    assert normalize_sittax_factor_r_percent(Decimal("28")) == Decimal("0.280000")
    assert normalize_sittax_factor_r_percent(Decimal("27.5")) == Decimal("0.275000")


def test_factor_r_assessment_table_shape(db_session) -> None:
    inspector = inspect(db_session.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("factor_r_assessments")}
    constraints = inspector.get_unique_constraints("factor_r_assessments")
    assert isinstance(columns["fs12_breakdown"]["type"], JSONB)
    assert columns["fs12_dominio_estimate"]["nullable"] is True
    assert any(
        item["name"] == "uq_factor_r_assessments_org_company_period"
        and item["column_names"] == ["organization_id", "external_company_id", "fiscal_period_id"]
        for item in constraints
    )


def test_partial_monetary_is_low_and_does_not_use_gross_total(db_session) -> None:
    movement = type("Movement", (), {"rubrics_summary": _summary(unclassified_code="13")})()
    coverage = PayrollCoverage(statuses={"2026-01": "MOVEMENT_FOUND"}, movements=(movement,))
    estimate = estimate_fs12_from_dominio(coverage)
    assert estimate.amount == Decimal("2400.00")
    assert estimate.confidence == FS12_LOW
    assert estimate.breakdown["unclassified_potentially_relevant"] == "500.00"
    assert estimate.can_raise_strong_reconciliation_alert is False


def test_reconciliation_dry_run_idempotence_and_org_isolation(db_session) -> None:
    org = _org(db_session, "factor-r-synthetic")
    other = _org(db_session, "factor-r-other")
    period = _period(db_session, org, "2026-07")
    _period(db_session, other, "2026-07")
    company = _company(db_session, org)
    _make_factor_r_potential(db_session, company)
    _company(db_session, other, "2")
    window = build_payroll_window("2026-07")
    for month in window.months:
        _movement(
            session=db_session,
            org=org,
            company=company,
            source_month=month,
            summary=_summary(thirteenth=Decimal("1000") if month.month == 12 else Decimal("0")),
        )
    _sittax(db_session, org, company, period)
    db_session.flush()

    dry_run = reconcile_factor_r_period(db_session, org, "2026-07", dry_run=True)
    assert dry_run.target_companies == 1
    assert dry_run.factor_r_calculated == 1
    assert db_session.scalars(select(FactorRAssessment)).all() == []
    assert db_session.scalars(select(FiscalAlert)).all() == []

    first = reconcile_factor_r_period(db_session, org, "2026-07")
    row = db_session.scalar(select(FactorRAssessment))
    assert first.assessments_created == 1
    assert row is not None
    assert row.fs12_confidence == FS12_MEDIUM
    assert row.factor_r_sittax_observed == Decimal("0.270000")
    assert row.sittax_observed_annexes == ["III", "V"]
    assert row.reconciliation_status == "THRESHOLD_DIVERGENCE"
    assert row.fs12_breakdown["total_estimated"] != "0.00"
    assert len(db_session.scalars(select(FiscalAlert)).all()) == 2

    second = reconcile_factor_r_period(db_session, org, "2026-07")
    assert second.assessments_created == 0
    assert second.assessments_updated == 0
    assert second.alerts_updated == 0
    assert len(db_session.scalars(select(FactorRAssessment)).all()) == 1
    assert len(db_session.scalars(select(FiscalAlert)).all()) == 2


def test_coverage_distinguishes_confirmed_zero_from_missing_and_rbt12_absent(db_session) -> None:
    org = _org(db_session, "factor-r-coverage")
    period = _period(db_session, org, "2026-07")
    company = _company(db_session, org)
    window = build_payroll_window("2026-07")
    for index, month in enumerate(window.months):
        if index < 9:
            _movement(session=db_session, org=org, company=company, source_month=month, summary=_summary())
        else:
            _report_without_movement(db_session, org, month)
    _sittax(db_session, org, company, period)
    db_session.flush()
    snapshot = db_session.scalar(select(SittaxApuracaoSnapshot))
    assert snapshot is not None
    snapshot.rbt12 = None

    reconcile_factor_r_period(db_session, org, "2026-07")
    row = db_session.scalar(select(FactorRAssessment))
    assert row is not None
    assert row.payroll_months_covered == 12
    assert row.payroll_months_with_movement == 9
    assert row.payroll_months_confirmed_zero == 3
    assert row.payroll_months_missing == 0
    assert row.factor_r_estimated_dominio is None
    assert row.calculation_status == "INSUFFICIENT_REVENUE_DATA"


def test_twelve_canonical_reports_without_movement_are_full_zero_coverage(db_session) -> None:
    org = _org(db_session, "factor-r-confirmed-zero")
    _period(db_session, org, "2026-07")
    _company(db_session, org)
    for month in build_payroll_window("2026-07").months:
        _report_without_movement(db_session, org, month)
    db_session.flush()

    result = reconcile_factor_r_period(db_session, org, "2026-07")
    row = db_session.scalar(select(FactorRAssessment))

    assert result.full_payroll_coverage == 1
    assert row is not None
    assert row.payroll_months_covered == 12
    assert row.payroll_months_with_movement == 0
    assert row.payroll_months_confirmed_zero == 12
    assert row.payroll_months_missing == 0
    assert row.fs12_dominio_estimate == Decimal("0.00")
    assert row.calculation_status == "INSUFFICIENT_REVENUE_DATA"


def test_one_missing_canonical_report_keeps_payroll_history_insufficient(db_session) -> None:
    org = _org(db_session, "factor-r-report-missing")
    _period(db_session, org, "2026-07")
    _company(db_session, org)
    months = build_payroll_window("2026-07").months
    for month in months[:-1]:
        _report_without_movement(db_session, org, month)
    db_session.flush()

    reconcile_factor_r_period(db_session, org, "2026-07")
    row = db_session.scalar(select(FactorRAssessment))

    assert row is not None
    assert row.payroll_months_covered == 11
    assert row.payroll_months_confirmed_zero == 11
    assert row.payroll_months_missing == 1
    assert row.fs12_dominio_estimate is None
    assert row.calculation_status == "INSUFFICIENT_PAYROLL_HISTORY"


def test_history_alert_is_idempotent_and_resolves_when_report_arrives(db_session) -> None:
    org = _org(db_session, "factor-r-history-alert")
    period = _period(db_session, org, "2026-07")
    company = _company(db_session, org)
    _make_factor_r_potential(db_session, company)
    months = build_payroll_window("2026-07").months
    for month in months[:-1]:
        _report_without_movement(db_session, org, month)
    _sittax(db_session, org, company, period)
    db_session.flush()
    snapshot = db_session.scalar(select(SittaxApuracaoSnapshot))
    assert snapshot is not None
    snapshot.annexes = []

    first = reconcile_factor_r_period(db_session, org, "2026-07")
    second = reconcile_factor_r_period(db_session, org, "2026-07")
    alert = db_session.scalar(select(FiscalAlert).where(FiscalAlert.code == "FACTOR_R_HISTORY_REQUIRED"))

    assert first.alerts_created == 1
    assert second.alerts_created == 0
    assert second.alerts_updated == 0
    assert alert is not None
    assert alert.status == "OPEN"

    _report_without_movement(db_session, org, months[-1])
    db_session.flush()
    resolved = reconcile_factor_r_period(db_session, org, "2026-07")
    db_session.refresh(alert)

    assert resolved.alerts_resolved == 1
    assert alert.status == "RESOLVED"


def test_sittax_metadata_is_preserved_when_payroll_history_is_incomplete(db_session) -> None:
    org = _org(db_session, "factor-r-sittax-with-history-gap")
    period = _period(db_session, org, "2026-07")
    company = _company(db_session, org)
    months = build_payroll_window("2026-07").months
    for month in months[1:]:
        _report_without_movement(db_session, org, month)
    _sittax(db_session, org, company, period)
    db_session.flush()

    reconcile_factor_r_period(db_session, org, "2026-07")
    row = db_session.scalar(select(FactorRAssessment))

    assert row is not None
    assert row.calculation_status == "INSUFFICIENT_PAYROLL_HISTORY"
    assert row.payroll_months_missing == 1
    assert row.rbt12_value == Decimal("100000.00")
    assert row.factor_r_sittax_observed == Decimal("0.270000")
    assert row.sittax_observed_annexes == ["III", "V"]


def test_sittax_snapshot_does_not_expand_the_cnae_target_universe(db_session) -> None:
    org = _org(db_session, "factor-r-sittax-not-target")
    period = _period(db_session, org, "2026-07")
    company = _company(db_session, org)
    _sittax(db_session, org, company, period)
    db_session.flush()

    result = reconcile_factor_r_period(db_session, org, "2026-07", dry_run=True)

    assert result.not_applicable == 0
    assert result.review == 1
    assert result.effective == 0
    assert result.target_companies == 1
