from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import Department, FiscalRegime
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.external_company import ExternalCompany
from backend.app.models.factor_r_assessment import FactorRAssessment
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.services.audit import record_audit_event
from backend.app.services.factor_r import get_company_factor_r_potential
from backend.app.services.integrations.acessorias.regime import resolve_acessorias_regime
from backend.app.services.integrations.dominio.monetary_summary import CATEGORY_ORDER


FACTOR_R_THRESHOLD = Decimal("0.28")
ZERO = Decimal("0.00")
NUMERIC_QUANTUM = Decimal("0.000001")

APPLICABILITY_NOT_APPLICABLE = "NOT_APPLICABLE"
APPLICABILITY_POTENTIAL = "POTENTIAL"
APPLICABILITY_EFFECTIVE = "EFFECTIVE"
APPLICABILITY_REVIEW = "REVIEW"

COVERAGE_MOVEMENT_FOUND = "MOVEMENT_FOUND"
COVERAGE_CONFIRMED_NO_MOVEMENT = "CONFIRMED_NO_MOVEMENT"
COVERAGE_REPORT_MISSING = "REPORT_MISSING"

FS12_HIGH = "HIGH"
FS12_MEDIUM = "MEDIUM"
FS12_LOW = "LOW"
FS12_INSUFFICIENT = "INSUFFICIENT"

CALCULATION_NOT_APPLICABLE = "NOT_APPLICABLE"
CALCULATION_COMPUTED = "COMPUTED"
CALCULATION_INSUFFICIENT_REVENUE = "INSUFFICIENT_REVENUE_DATA"
CALCULATION_INSUFFICIENT_HISTORY = "INSUFFICIENT_PAYROLL_HISTORY"
CALCULATION_REVIEW = "REVIEW"

RECONCILIATION_MATCH = "MATCH"
RECONCILIATION_POTENTIAL_ONLY = "POTENTIAL_ONLY"
RECONCILIATION_INSUFFICIENT = "INSUFFICIENT_DATA"
RECONCILIATION_THRESHOLD_DIVERGENCE = "THRESHOLD_DIVERGENCE"
RECONCILIATION_ANNEX_REVIEW = "ANNEX_REVIEW"
RECONCILIATION_REVIEW = "REVIEW"
RECONCILIATION_NOT_APPLICABLE = "NOT_APPLICABLE"

THRESHOLD_ABOVE_OR_EQUAL = "ABOVE_OR_EQUAL_28"
THRESHOLD_BELOW = "BELOW_28"

UNCLASSIFIED_NO = "NO_UNCLASSIFIED"
UNCLASSIFIED_ZERO_OR_IRRELEVANT = "UNCLASSIFIED_ZERO_OR_IRRELEVANT"
UNCLASSIFIED_POTENTIALLY_RELEVANT = "UNCLASSIFIED_POTENTIALLY_FS12_RELEVANT"
UNCLASSIFIED_UNKNOWN = "UNCLASSIFIED_UNKNOWN"

# These are the only positive-remuneration codes proven in the current Domínio contract.
# If one leaks into an unclassified bucket, it is unsafe to treat it as irrelevant.
POTENTIALLY_FS12_RELEVANT_UNCLASSIFIED_CODES = frozenset({"1", "13", "19", "100", "235"})
FACTOR_R_ALERT_CODES = frozenset(
    {
        "FACTOR_R_HISTORY_REQUIRED",
        "FACTOR_R_ESTIMATE_INCOMPLETE",
        "FACTOR_R_THRESHOLD_DIVERGENCE",
        "FACTOR_R_ANNEX_REVIEW",
    }
)


@dataclass(frozen=True, slots=True)
class PayrollWindow:
    start: date
    end: date
    months: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class PayrollCoverage:
    statuses: dict[str, str]
    movements: tuple[DominioPayrollCompanyMovement, ...]

    @property
    def covered(self) -> int:
        return sum(status != COVERAGE_REPORT_MISSING for status in self.statuses.values())

    @property
    def with_movement(self) -> int:
        return sum(status == COVERAGE_MOVEMENT_FOUND for status in self.statuses.values())

    @property
    def confirmed_zero(self) -> int:
        return sum(status == COVERAGE_CONFIRMED_NO_MOVEMENT for status in self.statuses.values())

    @property
    def missing(self) -> int:
        return sum(status == COVERAGE_REPORT_MISSING for status in self.statuses.values())


@dataclass(frozen=True, slots=True)
class Fs12Estimate:
    amount: Decimal | None
    confidence: str
    breakdown: dict[str, str]
    reason_codes: tuple[str, ...]
    coverage: PayrollCoverage
    unclassified_relevance: str
    can_compute_numeric_estimate: bool
    can_raise_strong_reconciliation_alert: bool


@dataclass(slots=True)
class FactorRReconciliationSummary:
    period: str
    dry_run: bool
    target_companies: int = 0
    potential: int = 0
    effective: int = 0
    review: int = 0
    not_applicable: int = 0
    full_payroll_coverage: int = 0
    partial_payroll_coverage: int = 0
    fs12_estimated: int = 0
    fs12_high: int = 0
    fs12_medium: int = 0
    fs12_low: int = 0
    fs12_insufficient: int = 0
    thirteenth_coverage_limitation: int = 0
    unclassified_relevant_limitation: int = 0
    sittax_snapshots: int = 0
    rbt12_available: int = 0
    sittax_factor_observed: int = 0
    annexes_observed: int = 0
    factor_r_calculated: int = 0
    above_or_equal_28: int = 0
    below_28: int = 0
    threshold_matches: int = 0
    threshold_divergences: int = 0
    near_threshold_low_confidence: int = 0
    annex_reviews: int = 0
    assessments_created: int = 0
    assessments_updated: int = 0
    alerts_created: int = 0
    alerts_updated: int = 0
    alerts_resolved: int = 0

    def to_dict(self) -> dict[str, int | str | bool]:
        return asdict(self)


def build_payroll_window(assessment_competence: str) -> PayrollWindow:
    year, month = _parse_competence(assessment_competence)
    end_year, end_month = _previous_month(year, month)
    months: list[date] = []
    current_year, current_month = end_year, end_month
    for _ in range(12):
        months.append(date(current_year, current_month, 1))
        current_year, current_month = _previous_month(current_year, current_month)
    months.reverse()
    return PayrollWindow(start=months[0], end=months[-1], months=tuple(months))


def calculate_factor_r(fs12: Decimal, rbt12: Decimal) -> Decimal:
    if rbt12 == ZERO:
        return FACTOR_R_THRESHOLD if fs12 > ZERO else Decimal("0.01")
    if fs12 == ZERO:
        return Decimal("0.01")
    return (fs12 / rbt12).quantize(NUMERIC_QUANTUM)


def classify_factor_r_threshold(value: Decimal) -> tuple[str, str]:
    if value >= FACTOR_R_THRESHOLD:
        return THRESHOLD_ABOVE_OR_EQUAL, "III"
    return THRESHOLD_BELOW, "V"


def normalize_sittax_factor_r_percent(value: Decimal | None) -> Decimal | None:
    """The persisted Sittax field is percentage points (e.g. 28 -> 0.28 ratio)."""
    if value is None:
        return None
    return (value / Decimal("100")).quantize(NUMERIC_QUANTUM)


def classify_unclassified_monetary(summary: dict[str, Any]) -> str:
    payload = summary.get("unclassified_monetary")
    if not isinstance(payload, dict):
        return UNCLASSIFIED_NO
    amount = _decimal(payload.get("amount"))
    count = payload.get("rubric_count")
    if amount == ZERO or count == 0:
        return UNCLASSIFIED_ZERO_OR_IRRELEVANT
    codes = {str(code) for code in payload.get("rubric_codes", []) if code is not None}
    if codes & POTENTIALLY_FS12_RELEVANT_UNCLASSIFIED_CODES:
        return UNCLASSIFIED_POTENTIALLY_RELEVANT
    return UNCLASSIFIED_UNKNOWN


def estimate_fs12_from_dominio(coverage: PayrollCoverage) -> Fs12Estimate:
    totals = {category: ZERO for category in CATEGORY_ORDER}
    reasons: set[str] = {"CASH_BASIS_UNVERIFIED"}
    schema_v2_count = 0
    unclassified = UNCLASSIFIED_NO
    unclassified_totals = {
        UNCLASSIFIED_POTENTIALLY_RELEVANT: ZERO,
        UNCLASSIFIED_UNKNOWN: ZERO,
    }
    thirteenth_present = False
    for movement in coverage.movements:
        summary = movement.rubrics_summary if isinstance(movement.rubrics_summary, dict) else {}
        if summary.get("schema_version") != 2:
            continue
        schema_v2_count += 1
        categories = summary.get("monetary_categories")
        if isinstance(categories, dict):
            for category in CATEGORY_ORDER:
                payload = categories.get(category)
                if isinstance(payload, dict):
                    totals[category] += _decimal(payload.get("amount"))
            thirteenth = categories.get("thirteenth_salary")
            thirteenth_present = thirteenth_present or (
                isinstance(thirteenth, dict) and _decimal(thirteenth.get("amount")) != ZERO
            )
        movement_unclassified = classify_unclassified_monetary(summary)
        unclassified = _combine_unclassified_relevance(unclassified, movement_unclassified)
        if movement_unclassified in unclassified_totals:
            unclassified_totals[movement_unclassified] += _decimal(
                (summary.get("unclassified_monetary") or {}).get("amount")
            )

    if coverage.missing:
        reasons.add("INSUFFICIENT_PAYROLL_HISTORY")
    if coverage.movements and schema_v2_count != len(coverage.movements):
        reasons.add("MONETARY_SCHEMA_V2_UNAVAILABLE")
    if not thirteenth_present:
        reasons.add("THIRTEENTH_SALARY_COVERAGE_UNVERIFIED")
    if unclassified == UNCLASSIFIED_POTENTIALLY_RELEVANT:
        reasons.add("UNCLASSIFIED_MONETARY_POTENTIALLY_FS12_RELEVANT")
    elif unclassified == UNCLASSIFIED_UNKNOWN:
        reasons.add("UNCLASSIFIED_MONETARY_UNKNOWN")

    can_compute = coverage.missing == 0 and schema_v2_count == len(coverage.movements)
    amount = sum(totals.values(), start=ZERO).quantize(Decimal("0.01")) if can_compute else None
    if not can_compute:
        confidence = FS12_INSUFFICIENT
    elif "THIRTEENTH_SALARY_COVERAGE_UNVERIFIED" in reasons or unclassified in {
        UNCLASSIFIED_POTENTIALLY_RELEVANT,
        UNCLASSIFIED_UNKNOWN,
    }:
        confidence = FS12_LOW
    else:
        # Observed CPP/FGTS and payroll competence do not prove payment/recollection cash basis.
        confidence = FS12_MEDIUM
    strong = confidence in {FS12_HIGH, FS12_MEDIUM} and unclassified in {
        UNCLASSIFIED_NO,
        UNCLASSIFIED_ZERO_OR_IRRELEVANT,
    }
    breakdown = {category: _decimal_text(totals[category]) for category in CATEGORY_ORDER}
    breakdown.update(
        {
            "unclassified_potentially_relevant": "0.00",
            "unclassified_unknown": "0.00",
            "total_estimated": _decimal_text(amount or ZERO),
        }
    )
    breakdown["unclassified_potentially_relevant"] = _decimal_text(
        unclassified_totals[UNCLASSIFIED_POTENTIALLY_RELEVANT]
    )
    breakdown["unclassified_unknown"] = _decimal_text(unclassified_totals[UNCLASSIFIED_UNKNOWN])
    return Fs12Estimate(
        amount=amount,
        confidence=confidence,
        breakdown=breakdown,
        reason_codes=tuple(sorted(reasons)),
        coverage=coverage,
        unclassified_relevance=unclassified,
        can_compute_numeric_estimate=can_compute,
        can_raise_strong_reconciliation_alert=strong,
    )


def reconcile_factor_r_period(
    session: Session,
    organization: Organization,
    assessment_competence: str,
    *,
    company_id: int | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> FactorRReconciliationSummary:
    period = _get_period(session, organization.id, assessment_competence)
    observed_now = now or datetime.now(timezone.utc)
    window = build_payroll_window(assessment_competence)
    summary = FactorRReconciliationSummary(period=assessment_competence, dry_run=dry_run)
    companies = _companies(session, organization.id, company_id)
    imports_by_month = _canonical_reports_by_month(session, organization.id, window)
    snapshots = _snapshot_map(session, organization.id, period.id)
    for company in companies:
        applicability, applicability_reasons = _resolve_applicability(session, organization.id, company, snapshots.get(company.id))
        _increment_applicability(summary, applicability)
        if applicability == APPLICABILITY_NOT_APPLICABLE:
            continue
        summary.target_companies += 1
        coverage = _build_coverage(session, organization.id, company.id, window, imports_by_month)
        estimate = estimate_fs12_from_dominio(coverage)
        snapshot = snapshots.get(company.id)
        assessment = _build_assessment(
            organization=organization,
            company=company,
            period=period,
            window=window,
            applicability=applicability,
            applicability_reasons=applicability_reasons,
            estimate=estimate,
            snapshot=snapshot,
        )
        _increment_assessment_summary(summary, assessment, estimate, snapshot)
        if not dry_run:
            _upsert_assessment(session, assessment, observed_now, summary)
        desired = _desired_alerts(assessment, estimate)
        _reconcile_alerts(
            session,
            summary=summary,
            organization_id=organization.id,
            company_id=company.id,
            period=period,
            desired=desired,
            dry_run=dry_run,
            observed_now=observed_now,
        )
    if not dry_run:
        record_audit_event(
            session,
            event_type="FACTOR_R_RECONCILIATION_RUN",
            message="Factor R reconciliation executed from persisted Domínio and Sittax data.",
            actor_type="system",
            actor_id="factor-r-cli",
            resource_type="organization",
            resource_id=str(organization.id),
            event_metadata=summary.to_dict(),
        )
        session.commit()
    return summary


def _build_assessment(
    *,
    organization: Organization,
    company: ExternalCompany,
    period: FiscalPeriod,
    window: PayrollWindow,
    applicability: str,
    applicability_reasons: tuple[str, ...],
    estimate: Fs12Estimate,
    snapshot: SittaxApuracaoSnapshot | None,
) -> dict[str, Any]:
    rbt12 = snapshot.rbt12 if snapshot is not None else None
    observed_factor = normalize_sittax_factor_r_percent(snapshot.factor_r_percent) if snapshot is not None else None
    observed_annexes = _extract_annexes(snapshot.annexes if snapshot is not None else None)
    calculated = None
    side = None
    annex = None
    if estimate.amount is not None and rbt12 is not None:
        calculated = calculate_factor_r(estimate.amount, rbt12)
        side, annex = classify_factor_r_threshold(calculated)
    reasons = set(applicability_reasons) | set(estimate.reason_codes)
    if rbt12 is None:
        reasons.add("INSUFFICIENT_REVENUE_DATA")
    if snapshot is None:
        reasons.add("SITTAX_SNAPSHOT_MISSING")
    if calculated is not None and estimate.confidence == FS12_LOW and abs(calculated - FACTOR_R_THRESHOLD) <= Decimal("0.01"):
        reasons.add("NEAR_THRESHOLD_LOW_CONFIDENCE")
    if calculated is not None and observed_factor is not None:
        observed_side, _ = classify_factor_r_threshold(observed_factor)
        if observed_side != side:
            reasons.add("THRESHOLD_SIDE_DIVERGENCE")
    if observed_annexes:
        reasons.add("SITTAX_ANNEXES_OBSERVED")
    calculation_status = (
        CALCULATION_NOT_APPLICABLE
        if applicability == APPLICABILITY_NOT_APPLICABLE
        else CALCULATION_COMPUTED
        if calculated is not None
        else CALCULATION_INSUFFICIENT_HISTORY
        if estimate.amount is None
        else CALCULATION_INSUFFICIENT_REVENUE
    )
    reconciliation = _reconciliation_status(
        applicability=applicability,
        calculated=calculated,
        observed_factor=observed_factor,
        observed_annexes=observed_annexes,
        estimate=estimate,
    )
    source_summary = {
        "schema_version": 1,
        "payroll": {
            "coverage": estimate.coverage.statuses,
            "schema_v2_expected": len(estimate.coverage.movements),
            "cash_basis_proven": False,
            "thirteenth_salary_coverage": "OBSERVED" if "THIRTEENTH_SALARY_COVERAGE_UNVERIFIED" not in reasons else "UNVERIFIED",
            "unclassified_relevance": estimate.unclassified_relevance,
        },
        "sittax": {
            "snapshot_present": snapshot is not None,
            "rbt12_present": rbt12 is not None,
            "factor_r_present": observed_factor is not None,
            "annexes_present": bool(observed_annexes),
            "factor_r_unit": "PERCENTAGE_POINTS_TO_RATIO" if observed_factor is not None else None,
        },
        "applicability": {"status": applicability, "reason_codes": sorted(applicability_reasons)},
    }
    values = {
        "organization_id": organization.id,
        "external_company_id": company.id,
        "fiscal_period_id": period.id,
        "applicability_status": applicability,
        "calculation_status": calculation_status,
        "payroll_window_start": window.start,
        "payroll_window_end": window.end,
        "payroll_months_expected": len(window.months),
        "payroll_months_covered": estimate.coverage.covered,
        "payroll_months_with_movement": estimate.coverage.with_movement,
        "payroll_months_confirmed_zero": estimate.coverage.confirmed_zero,
        "payroll_months_missing": estimate.coverage.missing,
        "fs12_dominio_estimate": estimate.amount,
        "fs12_confidence": estimate.confidence,
        "fs12_breakdown": estimate.breakdown,
        "rbt12_value": rbt12,
        "rbt12_source": "SITTAX" if rbt12 is not None else None,
        "rbt12_confidence": "OBSERVED" if rbt12 is not None else "INSUFFICIENT",
        "factor_r_estimated_dominio": calculated,
        "estimated_threshold_side": side,
        "estimated_annex": annex,
        "factor_r_sittax_observed": observed_factor,
        "sittax_observed_annexes": observed_annexes,
        "factor_r_delta": (calculated - observed_factor).quantize(NUMERIC_QUANTUM)
        if calculated is not None and observed_factor is not None
        else None,
        "reconciliation_status": reconciliation,
        "reason_codes": sorted(reasons),
        "source_summary": source_summary,
    }
    values["fingerprint"] = _fingerprint(**values)
    return values


def _resolve_applicability(
    session: Session,
    organization_id: int,
    company: ExternalCompany,
    snapshot: SittaxApuracaoSnapshot | None,
) -> tuple[str, tuple[str, ...]]:
    acessorias = session.scalar(
        select(AcessoriasCompanySnapshot).where(
            AcessoriasCompanySnapshot.organization_id == organization_id,
            AcessoriasCompanySnapshot.company_id == company.id,
        )
    )
    regime = resolve_acessorias_regime(acessorias.regime_raw or acessorias.regime_code) if acessorias else None
    canonical = regime.canonical if regime and regime.canonical else None
    if canonical == FiscalRegime.MEI.value:
        return APPLICABILITY_NOT_APPLICABLE, ("MEI_COMPANY",)
    if canonical and canonical != FiscalRegime.SIMPLES_NACIONAL.value:
        return APPLICABILITY_NOT_APPLICABLE, ("NOT_SIMPLES_NACIONAL",)
    potential = get_company_factor_r_potential(session, company_id=company.id)
    if canonical == FiscalRegime.SIMPLES_NACIONAL.value and potential.factor_r_potential is True:
        if snapshot is not None and snapshot.factor_r_percent is not None:
            return APPLICABILITY_EFFECTIVE, ("SIMPLES_FACTOR_R_CNAE_POTENTIAL", "SITTAX_FACTOR_R_OBSERVED")
        return APPLICABILITY_POTENTIAL, ("SIMPLES_FACTOR_R_CNAE_POTENTIAL",)
    if potential.factor_r_potential is False:
        return APPLICABILITY_NOT_APPLICABLE, ("FACTOR_R_CNAE_NOT_APPLICABLE",)
    return APPLICABILITY_REVIEW, ("FACTOR_R_APPLICABILITY_REVIEW",)


def _build_coverage(
    session: Session,
    organization_id: int,
    company_id: int,
    window: PayrollWindow,
    reports_by_month: dict[str, bool],
) -> PayrollCoverage:
    movements = tuple(
        session.scalars(
            select(DominioPayrollCompanyMovement)
            .where(
                DominioPayrollCompanyMovement.organization_id == organization_id,
                DominioPayrollCompanyMovement.external_company_id == company_id,
                DominioPayrollCompanyMovement.match_status == "MATCHED",
                DominioPayrollCompanyMovement.source_payroll_competence >= window.start,
                DominioPayrollCompanyMovement.source_payroll_competence <= window.end,
            )
            .order_by(DominioPayrollCompanyMovement.source_payroll_competence, DominioPayrollCompanyMovement.id)
        ).all()
    )
    movements_by_month: dict[str, list[DominioPayrollCompanyMovement]] = defaultdict(list)
    for movement in movements:
        if movement.source_payroll_competence is not None:
            movements_by_month[_competence_label(movement.source_payroll_competence)].append(movement)
    statuses: dict[str, str] = {}
    for month in window.months:
        label = _competence_label(month)
        statuses[label] = (
            COVERAGE_MOVEMENT_FOUND
            if movements_by_month[label]
            else COVERAGE_CONFIRMED_NO_MOVEMENT
            if reports_by_month.get(label)
            else COVERAGE_REPORT_MISSING
        )
    return PayrollCoverage(statuses=statuses, movements=movements)


def _canonical_reports_by_month(session: Session, organization_id: int, window: PayrollWindow) -> dict[str, bool]:
    """Return coverage only from the canonical full active-company report scope."""
    labels = {_competence_label(month) for month in window.months}
    reports: dict[str, bool] = {label: False for label in labels}
    imports = session.scalars(
        select(DominioPayrollImport).where(
            DominioPayrollImport.organization_id == organization_id,
            DominioPayrollImport.status.not_in(("FAILED", "PROCESSING")),
            DominioPayrollImport.selection_scope == "ACTIVE_COMPANIES",
        )
    ).all()
    for payroll_import in imports:
        for competence in payroll_import.source_competences or []:
            if competence in reports:
                reports[competence] = True
    return reports


def _snapshot_map(session: Session, organization_id: int, period_id: int) -> dict[int, SittaxApuracaoSnapshot]:
    return {
        row.external_company_id: row
        for row in session.scalars(
            select(SittaxApuracaoSnapshot).where(
                SittaxApuracaoSnapshot.organization_id == organization_id,
                SittaxApuracaoSnapshot.fiscal_period_id == period_id,
                SittaxApuracaoSnapshot.external_company_id.is_not(None),
            )
        ).all()
        if row.external_company_id is not None
    }


def _companies(session: Session, organization_id: int, company_id: int | None) -> list[ExternalCompany]:
    query = select(ExternalCompany).where(ExternalCompany.organization_id == organization_id, ExternalCompany.active.is_(True))
    if company_id is not None:
        query = query.where(ExternalCompany.id == company_id)
    return list(session.scalars(query.order_by(ExternalCompany.id)).all())


def _get_period(session: Session, organization_id: int, competence: str) -> FiscalPeriod:
    _parse_competence(competence)
    period = session.scalar(
        select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.competencia == competence)
    )
    if period is None:
        raise ValueError(f"FiscalPeriod '{competence}' was not found for this organization.")
    return period


def _reconciliation_status(
    *,
    applicability: str,
    calculated: Decimal | None,
    observed_factor: Decimal | None,
    observed_annexes: list[str],
    estimate: Fs12Estimate,
) -> str:
    if applicability == APPLICABILITY_NOT_APPLICABLE:
        return RECONCILIATION_NOT_APPLICABLE
    if calculated is None:
        return RECONCILIATION_INSUFFICIENT
    if observed_factor is not None:
        estimated_side, _ = classify_factor_r_threshold(calculated)
        observed_side, _ = classify_factor_r_threshold(observed_factor)
        if estimated_side != observed_side:
            return RECONCILIATION_THRESHOLD_DIVERGENCE
        if observed_annexes:
            return RECONCILIATION_ANNEX_REVIEW
        return RECONCILIATION_MATCH
    if observed_annexes:
        return RECONCILIATION_ANNEX_REVIEW
    return RECONCILIATION_POTENTIAL_ONLY if estimate.can_compute_numeric_estimate else RECONCILIATION_REVIEW


def _desired_alerts(assessment: dict[str, Any], estimate: Fs12Estimate) -> dict[str, tuple[str, str, str]]:
    if assessment["applicability_status"] != APPLICABILITY_EFFECTIVE:
        return {}
    alerts: dict[str, tuple[str, str, str]] = {}
    if assessment["payroll_months_missing"]:
        alerts["FACTOR_R_HISTORY_REQUIRED"] = (
            "Historico Domínio necessario para Fator R",
            "A janela de 12 meses possui relatorio Domínio ausente; mes ausente nao e tratado como zero.",
            "MEDIUM",
        )
    elif estimate.confidence in {FS12_LOW, FS12_INSUFFICIENT} or assessment["rbt12_value"] is None:
        alerts["FACTOR_R_ESTIMATE_INCOMPLETE"] = (
            "Estimativa de Fator R incompleta",
            "A estimativa usa somente componentes observados e possui limitacoes de cobertura ou receita.",
            "LOW",
        )
    if (
        assessment["reconciliation_status"] == RECONCILIATION_THRESHOLD_DIVERGENCE
        and estimate.can_raise_strong_reconciliation_alert
    ):
        alerts["FACTOR_R_THRESHOLD_DIVERGENCE"] = (
            "Divergencia de threshold do Fator R",
            "A estimativa Domínio e o Fator R observado no Sittax estao em lados opostos do threshold de 28%.",
            "MEDIUM",
        )
    if assessment["sittax_observed_annexes"]:
        alerts["FACTOR_R_ANNEX_REVIEW"] = (
            "Anexos Sittax requerem revisao de Fator R",
            "Os anexos observados nao identificam por si a receita submetida ao Fator R.",
            "LOW",
        )
    return alerts


def _upsert_assessment(
    session: Session, assessment: dict[str, Any], observed_now: datetime, summary: FactorRReconciliationSummary
) -> None:
    row = session.scalar(
        select(FactorRAssessment).where(
            FactorRAssessment.organization_id == assessment["organization_id"],
            FactorRAssessment.external_company_id == assessment["external_company_id"],
            FactorRAssessment.fiscal_period_id == assessment["fiscal_period_id"],
        )
    )
    values = {key: value for key, value in assessment.items() if key not in {"organization_id", "external_company_id", "fiscal_period_id"}}
    values["evaluated_at"] = observed_now
    if row is None:
        session.add(FactorRAssessment(**assessment, evaluated_at=observed_now))
        summary.assessments_created += 1
        return
    if row.fingerprint != assessment["fingerprint"]:
        for key, value in values.items():
            setattr(row, key, value)
        summary.assessments_updated += 1


def _reconcile_alerts(
    session: Session,
    *,
    summary: FactorRReconciliationSummary,
    organization_id: int,
    company_id: int,
    period: FiscalPeriod,
    desired: dict[str, tuple[str, str, str]],
    dry_run: bool,
    observed_now: datetime,
) -> None:
    existing = {
        row.code: row
        for row in session.scalars(
            select(FiscalAlert).where(
                FiscalAlert.organization_id == organization_id,
                FiscalAlert.company_id == company_id,
                FiscalAlert.period_id == period.id,
                FiscalAlert.code.in_(FACTOR_R_ALERT_CODES),
            )
        ).all()
    }
    for code, (title, message, severity) in desired.items():
        alert = existing.pop(code, None)
        if alert is None:
            summary.alerts_created += 1
            if not dry_run:
                session.add(
                    FiscalAlert(
                        organization_id=organization_id,
                        company_id=company_id,
                        period_id=period.id,
                        obligation_status_id=None,
                        code=code,
                        title=title,
                        message=message,
                        severity=severity,
                        department=Department.FISCAL.value,
                        source="LUMEN_FACTOR_R_RECONCILIATION",
                        status="OPEN",
                        rule_key=code,
                        details={"assessment_competence": period.competencia},
                    )
                )
        else:
            changed = any(
                (
                    alert.title != title,
                    alert.message != message,
                    alert.severity != severity,
                    alert.department != Department.FISCAL.value,
                    alert.source != "LUMEN_FACTOR_R_RECONCILIATION",
                    alert.status != "OPEN",
                    alert.resolved_at is not None,
                    alert.resolved_by is not None,
                    alert.resolution_notes is not None,
                )
            )
            if changed:
                summary.alerts_updated += 1
                if not dry_run:
                    alert.title = title
                    alert.message = message
                    alert.severity = severity
                    alert.department = Department.FISCAL.value
                    alert.source = "LUMEN_FACTOR_R_RECONCILIATION"
                    alert.status = "OPEN"
                    alert.resolved_at = None
                    alert.resolved_by = None
                    alert.resolution_notes = None
    for alert in existing.values():
        if alert.status != "RESOLVED":
            summary.alerts_resolved += 1
            if not dry_run:
                alert.status = "RESOLVED"
                alert.resolved_at = observed_now
                alert.resolved_by = "system"
                alert.resolution_notes = "Condition no longer applies after Factor R reconciliation."


def _increment_applicability(summary: FactorRReconciliationSummary, status: str) -> None:
    if status == APPLICABILITY_EFFECTIVE:
        summary.effective += 1
    elif status == APPLICABILITY_POTENTIAL:
        summary.potential += 1
    elif status == APPLICABILITY_REVIEW:
        summary.review += 1
    else:
        summary.not_applicable += 1


def _increment_assessment_summary(
    summary: FactorRReconciliationSummary,
    assessment: dict[str, Any],
    estimate: Fs12Estimate,
    snapshot: SittaxApuracaoSnapshot | None,
) -> None:
    summary.full_payroll_coverage += int(assessment["payroll_months_missing"] == 0)
    summary.partial_payroll_coverage += int(assessment["payroll_months_missing"] > 0)
    summary.fs12_estimated += int(estimate.amount is not None)
    summary.fs12_high += int(estimate.confidence == FS12_HIGH)
    summary.fs12_medium += int(estimate.confidence == FS12_MEDIUM)
    summary.fs12_low += int(estimate.confidence == FS12_LOW)
    summary.fs12_insufficient += int(estimate.confidence == FS12_INSUFFICIENT)
    summary.thirteenth_coverage_limitation += int("THIRTEENTH_SALARY_COVERAGE_UNVERIFIED" in estimate.reason_codes)
    summary.unclassified_relevant_limitation += int(
        estimate.unclassified_relevance in {UNCLASSIFIED_POTENTIALLY_RELEVANT, UNCLASSIFIED_UNKNOWN}
    )
    summary.sittax_snapshots += int(snapshot is not None)
    summary.rbt12_available += int(assessment["rbt12_value"] is not None)
    summary.sittax_factor_observed += int(assessment["factor_r_sittax_observed"] is not None)
    summary.annexes_observed += int(bool(assessment["sittax_observed_annexes"]))
    summary.factor_r_calculated += int(assessment["factor_r_estimated_dominio"] is not None)
    summary.above_or_equal_28 += int(assessment["estimated_threshold_side"] == THRESHOLD_ABOVE_OR_EQUAL)
    summary.below_28 += int(assessment["estimated_threshold_side"] == THRESHOLD_BELOW)
    summary.threshold_divergences += int(assessment["reconciliation_status"] == RECONCILIATION_THRESHOLD_DIVERGENCE)
    summary.threshold_matches += int(assessment["reconciliation_status"] == RECONCILIATION_MATCH)
    summary.near_threshold_low_confidence += int("NEAR_THRESHOLD_LOW_CONFIDENCE" in assessment["reason_codes"])
    summary.annex_reviews += int(assessment["reconciliation_status"] == RECONCILIATION_ANNEX_REVIEW)


def _extract_annexes(payload: list[dict[str, Any]] | None) -> list[str]:
    annexes: set[str] = set()
    for item in payload or []:
        if not isinstance(item, dict):
            continue
        value = item.get("anexo") or item.get("anexoApuracao")
        if isinstance(value, dict):
            value = value.get("nome") or value.get("codigo")
        match = re.search(r"(?:ANEXO[_ ]*)?(I|II|III|IV|V|VI)\b", str(value).upper()) if value is not None else None
        if match:
            annexes.add(match.group(1))
    return sorted(annexes)


def _combine_unclassified_relevance(current: str, incoming: str) -> str:
    ordering = {
        UNCLASSIFIED_NO: 0,
        UNCLASSIFIED_ZERO_OR_IRRELEVANT: 1,
        UNCLASSIFIED_UNKNOWN: 2,
        UNCLASSIFIED_POTENTIALLY_RELEVANT: 3,
    }
    return incoming if ordering[incoming] > ordering[current] else current


def _fingerprint(**values: object) -> str:
    canonical = json.dumps(values, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decimal(value: object) -> Decimal:
    if value is None or value == "":
        return ZERO
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _decimal_text(value: Decimal) -> str:
    return value.quantize(Decimal("0.01")).to_eng_string()


def _parse_competence(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if match is None or not 1 <= int(match.group(2)) <= 12:
        raise ValueError("Competence must be in YYYY-MM format.")
    return int(match.group(1)), int(match.group(2))


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _competence_label(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"
