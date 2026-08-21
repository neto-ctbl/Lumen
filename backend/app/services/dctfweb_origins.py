from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import Department
from backend.app.models.dctfweb_origin import (
    DctfwebClassificationConfidence,
    DctfwebDpCoverageStatus,
    DctfwebExpectedOrigin,
    DctfwebOriginAssessment,
)
from backend.app.models.acessorias_delivery_snapshot import AcessoriasDeliverySnapshot
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.services.audit import record_audit_event
from backend.app.services.integrations.dominio.contracts import DominioSelectionScope


DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED = "DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED"
DCTFWEB_DP_EXPECTED_NOT_FOUND = "DCTFWEB_DP_EXPECTED_NOT_FOUND"
DCTFWEB_SHARED_ORIGIN_DETECTED = "DCTFWEB_SHARED_ORIGIN_DETECTED"
DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED = "DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED"
DCTFWEB_ORIGIN_UNDETERMINED = "DCTFWEB_ORIGIN_UNDETERMINED"
MIT_START_YEAR = 2025
MIT_START_MONTH = 1
REINF_OBLIGATION_CODES = frozenset({"REINF"})
MIT_OBLIGATION_REASON_CODES = {
    "PIS": "MIT_PIS_COFINS_SIGNAL",
    "COFINS": "MIT_PIS_COFINS_SIGNAL",
}
MIT_OBLIGATION_CODES = frozenset(MIT_OBLIGATION_REASON_CODES)
S9_3_ALERT_CODES = frozenset(
    {
        DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
        DCTFWEB_DP_EXPECTED_NOT_FOUND,
        DCTFWEB_SHARED_ORIGIN_DETECTED,
        DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED,
        DCTFWEB_ORIGIN_UNDETERMINED,
    }
)


@dataclass(frozen=True, slots=True)
class SignalDetection:
    present: bool
    reason_codes: tuple[str, ...]
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class OriginDecision:
    origin: str
    department: str | None
    confidence: str
    reason_codes: tuple[str, ...]


@dataclass(slots=True)
class DctfwebReconciliationSummary:
    period: str
    dry_run: bool
    companies_evaluated: int = 0
    dp: int = 0
    fiscal: int = 0
    shared: int = 0
    undetermined: int = 0
    reinf_signal_companies: int = 0
    mit_signal_companies: int = 0
    dctfweb_observed: int = 0
    dominio_report_missing: int = 0
    alerts_created: int = 0
    alerts_updated: int = 0
    alerts_resolved: int = 0

    def to_dict(self) -> dict[str, int | str | bool]:
        return {
            "period": self.period,
            "dry_run": self.dry_run,
            "companies_evaluated": self.companies_evaluated,
            "dp": self.dp,
            "fiscal": self.fiscal,
            "shared": self.shared,
            "undetermined": self.undetermined,
            "reinf_signal_companies": self.reinf_signal_companies,
            "mit_signal_companies": self.mit_signal_companies,
            "dctfweb_observed": self.dctfweb_observed,
            "dominio_report_missing": self.dominio_report_missing,
            "alerts_created": self.alerts_created,
            "alerts_updated": self.alerts_updated,
            "alerts_resolved": self.alerts_resolved,
        }


def detect_dp_component(movements: Iterable[DominioPayrollCompanyMovement]) -> SignalDetection:
    items = list(movements)
    codes: set[str] = set()
    for movement in items:
        if movement.has_payroll:
            codes.add("DOMINIO_PAYROLL_MOVEMENT")
        if movement.has_employee:
            codes.add("DOMINIO_EMPLOYEE")
        if movement.has_pro_labore:
            codes.add("DOMINIO_PRO_LABORE")
        if movement.has_autonomous:
            codes.add("DOMINIO_AUTONOMOUS")
        if movement.has_inss:
            codes.add("DOMINIO_INSS")
        if movement.has_termination:
            codes.add("DOMINIO_TERMINATION")
        if movement.has_vacation:
            codes.add("DOMINIO_VACATION")
        if movement.has_leave:
            codes.add("DOMINIO_LEAVE")
        if movement.has_fgts:
            codes.add("DOMINIO_FGTS_SUPPORT")
    decisive = codes - {"DOMINIO_FGTS_SUPPORT"}
    return SignalDetection(
        present=bool(decisive),
        reason_codes=tuple(sorted(codes)),
        summary={"movement_count": len(items), "signal_codes": sorted(codes)},
    )


def detect_reinf_component(
    session: Session, *, organization_id: int, company_id: int, period_id: int
) -> SignalDetection:
    status_codes = set(
        session.scalars(
            select(FiscalObligation.code)
            .join(FiscalObligationStatus, FiscalObligationStatus.obligation_id == FiscalObligation.id)
            .where(
                FiscalObligationStatus.organization_id == organization_id,
                FiscalObligationStatus.company_id == company_id,
                FiscalObligationStatus.period_id == period_id,
                FiscalObligation.code.in_(REINF_OBLIGATION_CODES),
            )
        ).all()
    )
    evidence_codes = set(
        session.scalars(
            select(FiscalEvidence.detected_obligation).where(
                FiscalEvidence.organization_id == organization_id,
                FiscalEvidence.company_id == company_id,
                FiscalEvidence.period_id == period_id,
                FiscalEvidence.detected_obligation.in_(REINF_OBLIGATION_CODES),
            )
        ).all()
    )
    codes = sorted(status_codes | evidence_codes)
    return SignalDetection(
        present=bool(codes),
        reason_codes=("REINF_SIGNAL",) if codes else (),
        summary={"signal_count": len(codes), "obligation_codes": codes},
    )


def detect_mit_component(
    session: Session, *, organization_id: int, company_id: int, period: FiscalPeriod
) -> SignalDetection:
    if (period.year, period.month) < (MIT_START_YEAR, MIT_START_MONTH):
        return SignalDetection(
            present=False,
            reason_codes=(),
            summary={"signal": False, "obligation_codes": [], "minimum_competence": "2025-01"},
        )

    status_codes = set(
        session.scalars(
            select(FiscalObligation.code)
            .join(FiscalObligationStatus, FiscalObligationStatus.obligation_id == FiscalObligation.id)
            .where(
                FiscalObligationStatus.organization_id == organization_id,
                FiscalObligationStatus.company_id == company_id,
                FiscalObligationStatus.period_id == period.id,
                FiscalObligation.code.in_(MIT_OBLIGATION_CODES),
            )
        ).all()
    )
    evidence_codes = set(
        session.scalars(
            select(FiscalEvidence.detected_obligation).where(
                FiscalEvidence.organization_id == organization_id,
                FiscalEvidence.company_id == company_id,
                FiscalEvidence.period_id == period.id,
                FiscalEvidence.detected_obligation.in_(MIT_OBLIGATION_CODES),
            )
        ).all()
    )
    codes = sorted(status_codes | evidence_codes)
    reason_codes = sorted({MIT_OBLIGATION_REASON_CODES[code] for code in codes})
    if codes:
        reason_codes.append("MIT_SIGNAL")
    return SignalDetection(
        present=bool(codes),
        reason_codes=tuple(sorted(reason_codes)),
        summary={"signal": bool(codes), "obligation_codes": codes},
    )


def detect_dctfweb_observation(
    session: Session, *, organization_id: int, company_id: int, period_id: int
) -> SignalDetection:
    status_exists = session.scalar(
        select(FiscalObligationStatus.id)
        .join(FiscalObligation, FiscalObligationStatus.obligation_id == FiscalObligation.id)
        .where(
            FiscalObligationStatus.organization_id == organization_id,
            FiscalObligationStatus.company_id == company_id,
            FiscalObligationStatus.period_id == period_id,
            FiscalObligation.code == "DCTFWEB",
        )
        .limit(1)
    )
    evidence_exists = session.scalar(
        select(FiscalEvidence.id)
        .where(
            FiscalEvidence.organization_id == organization_id,
            FiscalEvidence.company_id == company_id,
            FiscalEvidence.period_id == period_id,
            FiscalEvidence.detected_obligation == "DCTFWEB",
        )
        .limit(1)
    )
    acessorias_delivery_exists = session.scalar(
        select(AcessoriasDeliverySnapshot.id)
        .join(FiscalObligation, AcessoriasDeliverySnapshot.obligation_id == FiscalObligation.id)
        .where(
            AcessoriasDeliverySnapshot.organization_id == organization_id,
            AcessoriasDeliverySnapshot.company_id == company_id,
            AcessoriasDeliverySnapshot.period_id == period_id,
            FiscalObligation.code == "DCTFWEB",
        )
        .limit(1)
    )
    observed = status_exists is not None or evidence_exists is not None or acessorias_delivery_exists is not None
    return SignalDetection(
        present=observed,
        reason_codes=("DCTFWEB_OBSERVED",) if observed else (),
        summary={"observed": observed},
    )


def decide_dctfweb_origin(
    *,
    dp_coverage_status: str,
    dp: SignalDetection,
    reinf: SignalDetection,
    mit: SignalDetection,
    dctfweb: SignalDetection,
) -> OriginDecision:
    fiscal_present = reinf.present or mit.present
    codes = set(dp.reason_codes) | set(reinf.reason_codes) | set(mit.reason_codes) | set(dctfweb.reason_codes)
    if dp.present and fiscal_present:
        codes.add("DP_AND_FISCAL_COMPONENTS")
        return OriginDecision(
            DctfwebExpectedOrigin.COMPARTILHADO.value,
            Department.COMPARTILHADO.value,
            DctfwebClassificationConfidence.HIGH.value,
            tuple(sorted(codes)),
        )
    if dp.present:
        return OriginDecision(
            DctfwebExpectedOrigin.DP.value,
            Department.DP.value,
            DctfwebClassificationConfidence.HIGH.value,
            tuple(sorted(codes)),
        )
    if fiscal_present and dp_coverage_status == DctfwebDpCoverageStatus.CONFIRMED_NO_MOVEMENT.value:
        return OriginDecision(
            DctfwebExpectedOrigin.FISCAL.value,
            Department.FISCAL.value,
            DctfwebClassificationConfidence.HIGH.value,
            tuple(sorted(codes | {"DOMINIO_CONFIRMED_NO_MOVEMENT"})),
        )
    if fiscal_present and dp_coverage_status == DctfwebDpCoverageStatus.REPORT_MISSING.value:
        return OriginDecision(
            DctfwebExpectedOrigin.UNDETERMINED.value,
            None,
            DctfwebClassificationConfidence.LOW.value,
            tuple(sorted(codes | {"DOMINIO_COVERAGE_MISSING"})),
        )
    if dctfweb.present:
        return OriginDecision(
            DctfwebExpectedOrigin.UNDETERMINED.value,
            None,
            DctfwebClassificationConfidence.LOW.value,
            tuple(sorted(codes | {"DCTFWEB_WITHOUT_ORIGIN_SIGNAL"})),
        )
    if dp_coverage_status == DctfwebDpCoverageStatus.REPORT_MISSING.value:
        return OriginDecision(
            DctfwebExpectedOrigin.UNDETERMINED.value,
            None,
            DctfwebClassificationConfidence.LOW.value,
            ("DOMINIO_COVERAGE_MISSING", "NO_DCTFWEB_COMPONENT_OBSERVED"),
        )
    return OriginDecision(
        DctfwebExpectedOrigin.UNDETERMINED.value,
        None,
        DctfwebClassificationConfidence.LOW.value,
        ("NO_DCTFWEB_COMPONENT_OBSERVED",),
    )


def reconcile_dctfweb_period(
    session: Session,
    organization: Organization,
    assessment_competence: str,
    *,
    external_company_id: int | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> DctfwebReconciliationSummary:
    period = _get_period(session, organization.id, assessment_competence)
    observed_now = now or datetime.now(timezone.utc)
    summary = DctfwebReconciliationSummary(period=assessment_competence, dry_run=dry_run)
    company_query = select(ExternalCompany).where(
        ExternalCompany.organization_id == organization.id,
        ExternalCompany.active.is_(True),
    )
    if external_company_id is not None:
        company_query = company_query.where(ExternalCompany.id == external_company_id)
    companies = session.scalars(company_query.order_by(ExternalCompany.id)).all()
    canonical_imports = list(
        session.scalars(
            select(DominioPayrollImport).where(
                DominioPayrollImport.organization_id == organization.id,
                DominioPayrollImport.assessment_period_id == period.id,
                DominioPayrollImport.selection_scope == DominioSelectionScope.ACTIVE_COMPANIES.value,
                DominioPayrollImport.status.not_in(("FAILED", "PROCESSING")),
            )
        ).all()
    )
    for company in companies:
        movements = _canonical_movements(session, organization.id, company.id, period.id, canonical_imports)
        coverage = (
            DctfwebDpCoverageStatus.CONFIRMED_MOVEMENT.value
            if movements
            else DctfwebDpCoverageStatus.CONFIRMED_NO_MOVEMENT.value
            if canonical_imports
            else DctfwebDpCoverageStatus.REPORT_MISSING.value
        )
        dp = detect_dp_component(movements)
        reinf = detect_reinf_component(session, organization_id=organization.id, company_id=company.id, period_id=period.id)
        mit = detect_mit_component(session, organization_id=organization.id, company_id=company.id, period=period)
        dctfweb = detect_dctfweb_observation(
            session, organization_id=organization.id, company_id=company.id, period_id=period.id
        )
        decision = decide_dctfweb_origin(
            dp_coverage_status=coverage, dp=dp, reinf=reinf, mit=mit, dctfweb=dctfweb
        )
        summary.companies_evaluated += 1
        _increment_origin(summary, decision.origin)
        summary.reinf_signal_companies += int(reinf.present)
        summary.mit_signal_companies += int(mit.present)
        summary.dctfweb_observed += int(dctfweb.present)
        summary.dominio_report_missing += int(coverage == DctfwebDpCoverageStatus.REPORT_MISSING.value)
        source_competence = min((movement.source_payroll_competence for movement in movements if movement.source_payroll_competence), default=None)
        source_summary = {
            "schema_version": 1,
            "dp": {"coverage": coverage, "esocial_signal": dp.present, **dp.summary},
            "fiscal": {
                "reinf": {"signal": reinf.present, **reinf.summary},
                "mit": mit.summary,
            },
            "dctfweb": dctfweb.summary,
        }
        fingerprint = build_assessment_fingerprint(
            organization_id=organization.id,
            external_company_id=company.id,
            assessment_competence=assessment_competence,
            source_payroll_competence=source_competence,
            dp_coverage_status=coverage,
            dp_signal_present=dp.present,
            reinf_signal_present=reinf.present,
            mit_signal_present=mit.present,
            fiscal_signal_present=reinf.present or mit.present,
            dctfweb_observed=dctfweb.present,
            expected_origin=decision.origin,
            reason_codes=decision.reason_codes,
        )
        if not dry_run:
            _upsert_assessment(
                session,
                organization_id=organization.id,
                company_id=company.id,
                period=period,
                source_competence=source_competence,
                coverage=coverage,
                dp=dp,
                reinf=reinf,
                mit=mit,
                dctfweb=dctfweb,
                decision=decision,
                source_summary=source_summary,
                fingerprint=fingerprint,
                observed_now=observed_now,
            )
        desired_alerts = _desired_alerts(
            period=period,
            coverage=coverage,
            decision=decision,
            dctfweb_observed=dctfweb.present,
            fiscal_signal_present=reinf.present or mit.present,
        )
        if _previous_period_requires_review(session, organization.id, company.id, period):
            desired_alerts[DCTFWEB_NEXT_MONTH_REVIEW_REQUIRED] = (
                "Revisao mensal da DCTFWeb necessaria",
                "A competencia anterior teve componente DP/eSocial esperado e requer revisao operacional neste mes.",
                "LOW",
                Department.SISTEMA.value,
            )
        _reconcile_alerts(
            session,
            summary=summary,
            organization_id=organization.id,
            company_id=company.id,
            period=period,
            desired=desired_alerts,
            dry_run=dry_run,
            observed_now=observed_now,
        )
    _reconcile_monthly_report_alert(
        session,
        summary=summary,
        organization_id=organization.id,
        period=period,
        missing=not canonical_imports,
        dry_run=dry_run,
        observed_now=observed_now,
    )
    if not dry_run:
        record_audit_event(
            session,
            event_type="DCTFWEB_ORIGIN_RECONCILIATION_RUN",
            message="DCTFWeb origin reconciliation executed.",
            actor_type="system",
            actor_id="dctfweb-origin-cli",
            resource_type="organization",
            resource_id=str(organization.id),
            event_metadata=summary.to_dict(),
        )
        session.commit()
    return summary


def build_assessment_fingerprint(**values: object) -> str:
    canonical = json.dumps(values, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_period(session: Session, organization_id: int, competence: str) -> FiscalPeriod:
    period = session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.organization_id == organization_id, FiscalPeriod.competencia == competence
        )
    )
    if period is None:
        raise ValueError(f"FiscalPeriod '{competence}' was not found for this organization.")
    return period


def _canonical_movements(
    session: Session, organization_id: int, company_id: int, period_id: int, imports: list[DominioPayrollImport]
) -> list[DominioPayrollCompanyMovement]:
    if not imports:
        return []
    return list(
        session.scalars(
            select(DominioPayrollCompanyMovement)
            .where(
                DominioPayrollCompanyMovement.organization_id == organization_id,
                DominioPayrollCompanyMovement.external_company_id == company_id,
                DominioPayrollCompanyMovement.fiscal_period_id == period_id,
                DominioPayrollCompanyMovement.import_id.in_([item.id for item in imports]),
                DominioPayrollCompanyMovement.match_status == "MATCHED",
            )
            .order_by(DominioPayrollCompanyMovement.id)
        ).all()
    )


def _increment_origin(summary: DctfwebReconciliationSummary, origin: str) -> None:
    if origin == DctfwebExpectedOrigin.DP.value:
        summary.dp += 1
    elif origin == DctfwebExpectedOrigin.FISCAL.value:
        summary.fiscal += 1
    elif origin == DctfwebExpectedOrigin.COMPARTILHADO.value:
        summary.shared += 1
    else:
        summary.undetermined += 1


def _upsert_assessment(
    session: Session,
    *,
    organization_id: int,
    company_id: int,
    period: FiscalPeriod,
    source_competence: date | None,
    coverage: str,
    dp: SignalDetection,
    reinf: SignalDetection,
    mit: SignalDetection,
    dctfweb: SignalDetection,
    decision: OriginDecision,
    source_summary: dict[str, object],
    fingerprint: str,
    observed_now: datetime,
) -> None:
    row = session.scalar(
        select(DctfwebOriginAssessment).where(
            DctfwebOriginAssessment.organization_id == organization_id,
            DctfwebOriginAssessment.external_company_id == company_id,
            DctfwebOriginAssessment.fiscal_period_id == period.id,
        )
    )
    values = {
        "assessment_competence": date(period.year, period.month, 1),
        "source_payroll_competence": source_competence,
        "dp_coverage_status": coverage,
        "dp_signal_present": dp.present,
        "reinf_signal_present": reinf.present,
        "mit_signal_present": mit.present,
        "fiscal_signal_present": reinf.present or mit.present,
        "dctfweb_observed": dctfweb.present,
        "expected_origin": decision.origin,
        "expected_responsible_department": decision.department,
        "classification_confidence": decision.confidence,
        "reason_codes": list(decision.reason_codes),
        "source_summary": source_summary,
        "fingerprint": fingerprint,
        "evaluated_at": observed_now,
    }
    if row is None:
        session.add(
            DctfwebOriginAssessment(
                organization_id=organization_id,
                external_company_id=company_id,
                fiscal_period_id=period.id,
                **values,
            )
        )
    else:
        for key, value in values.items():
            setattr(row, key, value)


def _desired_alerts(
    *,
    period: FiscalPeriod,
    coverage: str,
    decision: OriginDecision,
    dctfweb_observed: bool,
    fiscal_signal_present: bool,
) -> dict[str, tuple[str, str, str, str]]:
    alerts: dict[str, tuple[str, str, str, str]] = {}
    if decision.origin == DctfwebExpectedOrigin.COMPARTILHADO.value:
        alerts[DCTFWEB_SHARED_ORIGIN_DETECTED] = (
            "Origem compartilhada da DCTFWeb",
            "Ha componentes DP/eSocial e Fiscal esperados na mesma DCTFWeb.",
            "LOW",
            Department.COMPARTILHADO.value,
        )
    # The project has no canonical DCTFWeb due-date representation yet. Do not emit
    # an absence alert prematurely; the next-month operational review remains active.
    if decision.origin == DctfwebExpectedOrigin.UNDETERMINED.value and (
        dctfweb_observed or (coverage == DctfwebDpCoverageStatus.REPORT_MISSING.value and fiscal_signal_present)
    ):
        alerts[DCTFWEB_ORIGIN_UNDETERMINED] = (
            "Origem da DCTFWeb indeterminada",
            "A origem esperada da DCTFWeb requer revisao operacional das fontes disponiveis.",
            "LOW",
            Department.SISTEMA.value,
        )
    return alerts


def _monthly_report_alert_payload(period: FiscalPeriod) -> tuple[str, str, str, str]:
    source_payroll_competence = _previous_competence_label(period)
    return (
        "Relatorio mensal Dominio necessario",
        f"O relatorio mensal Dominio da folha {source_payroll_competence} ainda nao foi importado. "
        f"Apuracao relacionada: {period.competencia}.",
        "MEDIUM",
        Department.SISTEMA.value,
    )


def _reconcile_monthly_report_alert(
    session: Session,
    *,
    summary: DctfwebReconciliationSummary,
    organization_id: int,
    period: FiscalPeriod,
    missing: bool,
    dry_run: bool,
    observed_now: datetime,
) -> None:
    existing = session.scalars(
        select(FiscalAlert).where(
            FiscalAlert.organization_id == organization_id,
            FiscalAlert.period_id == period.id,
            FiscalAlert.code == DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
        )
    ).all()
    singleton = next((alert for alert in existing if alert.company_id is None), None)
    extras = [alert for alert in existing if alert.company_id is not None]

    if missing:
        title, message, severity, department = _monthly_report_alert_payload(period)
        if singleton is None:
            summary.alerts_created += 1
            if not dry_run:
                session.add(
                    FiscalAlert(
                        organization_id=organization_id,
                        company_id=None,
                        period_id=period.id,
                        obligation_status_id=None,
                        code=DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
                        title=title,
                        message=message,
                        severity=severity,
                        department=department,
                        source="LUMEN_DCTFWEB_RECONCILIATION",
                        status="OPEN",
                        rule_key=DOMINIO_MONTHLY_ACTIVE_REPORT_REQUIRED,
                        details={"assessment_competence": period.competencia},
                    )
                )
        else:
            summary.alerts_updated += 1
            if not dry_run:
                singleton.title = title
                singleton.message = message
                singleton.severity = severity
                singleton.department = department
                singleton.source = "LUMEN_DCTFWEB_RECONCILIATION"
                singleton.status = "OPEN"
                singleton.resolved_at = None
                singleton.resolved_by = None
                singleton.resolution_notes = None

    alerts_to_resolve = extras if missing else existing
    for alert in alerts_to_resolve:
        if alert.status != "RESOLVED":
            summary.alerts_resolved += 1
            if not dry_run:
                alert.status = "RESOLVED"
                alert.resolved_at = observed_now
                alert.resolved_by = "system"
                alert.resolution_notes = "Condition no longer applies after reconciliation."


def _previous_competence_label(period: FiscalPeriod) -> str:
    year = period.year if period.month > 1 else period.year - 1
    month = period.month - 1 if period.month > 1 else 12
    return f"{month:02d}/{year:04d}"


def _previous_period_requires_review(
    session: Session, organization_id: int, company_id: int, period: FiscalPeriod
) -> bool:
    previous_year = period.year if period.month > 1 else period.year - 1
    previous_month = period.month - 1 if period.month > 1 else 12
    previous = session.scalar(
        select(DctfwebOriginAssessment.expected_origin)
        .join(FiscalPeriod, FiscalPeriod.id == DctfwebOriginAssessment.fiscal_period_id)
        .where(
            DctfwebOriginAssessment.organization_id == organization_id,
            DctfwebOriginAssessment.external_company_id == company_id,
            FiscalPeriod.year == previous_year,
            FiscalPeriod.month == previous_month,
        )
    )
    return previous in {DctfwebExpectedOrigin.DP.value, DctfwebExpectedOrigin.COMPARTILHADO.value}


def _reconcile_alerts(
    session: Session,
    *,
    summary: DctfwebReconciliationSummary,
    organization_id: int,
    company_id: int,
    period: FiscalPeriod,
    desired: dict[str, tuple[str, str, str, str]],
    dry_run: bool,
    observed_now: datetime,
) -> None:
    existing = {
        alert.code: alert
        for alert in session.scalars(
            select(FiscalAlert).where(
                FiscalAlert.organization_id == organization_id,
                FiscalAlert.company_id == company_id,
                FiscalAlert.period_id == period.id,
                FiscalAlert.code.in_(S9_3_ALERT_CODES),
            )
        ).all()
    }
    for code, (title, message, severity, department) in desired.items():
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
                        department=department,
                        source="LUMEN_DCTFWEB_RECONCILIATION",
                        status="OPEN",
                        rule_key=code,
                        details={"assessment_competence": period.competencia},
                    )
                )
        else:
            summary.alerts_updated += 1
            if not dry_run:
                alert.title = title
                alert.message = message
                alert.severity = severity
                alert.department = department
                alert.source = "LUMEN_DCTFWEB_RECONCILIATION"
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
                alert.resolution_notes = "Condition no longer applies after reconciliation."
