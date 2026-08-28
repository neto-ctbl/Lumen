from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.enums import FISCAL_REGIME_LABELS, FiscalRegime
from backend.app.core.config import get_settings
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.dctfweb_origin import DctfwebOriginAssessment
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement, DominioPayrollImport
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.factor_r_assessment import FactorRAssessment
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_installment import FiscalInstallment
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_account import IntegrationAccount
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_difal_snapshot import SittaxDifalSnapshot
from backend.app.models.sittax_fiscal_document_snapshot import SittaxFiscalDocumentSnapshot
from backend.app.models.sittax_task_snapshot import SittaxTaskSnapshot
from backend.app.schemas.cockpit import CockpitCompanyRow, CockpitResponse
from backend.app.schemas.company import (
    CompanyDetailResponse,
    CompanyListResponse,
    CompanyObligationPreview,
    CompanySummary,
    CompanySummaryKpis,
)
from backend.app.schemas.econet import CompanyCnaeItemResponse, CompanyCnaeListResponse, FactorRPotentialResponse
from backend.app.schemas.dashboard import (
    DashboardDctfwebSummary,
    DashboardDepartmentSummary,
    DashboardFactorRSummary,
    DashboardKpis,
    DashboardResponse,
    DashboardStatusSummary,
)
from backend.app.schemas.delivery import DeliveryItem, DeliveryListResponse
from backend.app.schemas.divergence import DivergenceItem, DivergenceListResponse
from backend.app.schemas.evidence import EvidenceItem, EvidenceListResponse
from backend.app.schemas.installment import InstallmentItem, InstallmentListResponse
from backend.app.schemas.integration import IntegrationHealthItem, IntegrationHealthResponse
from backend.app.schemas.lumen_s9 import (
    DctfwebOriginItem,
    DctfwebOriginListResponse,
    DctfwebSummaryResponse,
    DominioMonetarySummary,
    DominioPayrollCompanyResponse,
    DominioPayrollSignals,
    DominioPayrollSummaryResponse,
    FactorRDetailResponse,
    FactorRItem,
    FactorRListResponse,
    FactorRSummaryResponse,
)
from backend.app.schemas.period import PeriodItem, PeriodListResponse
from backend.app.services.integrations.econet.assisted_session import get_econet_assisted_session
from backend.app.services.integrations.econet.parser import CURRENT_ECONET_PARSER_VERSION
from backend.app.services.factor_r import get_company_factor_r_potential as compute_company_factor_r_potential
from backend.app.services.integrations.dominio.monetary_summary import (
    MONETARY_SUMMARY_COMPLETE,
    MONETARY_SUMMARY_INSUFFICIENT,
    MONETARY_SUMMARY_PARTIAL,
)


STALE_RUN_MINUTES = 15
TERMINAL_RUN_STATUSES = {"SUCCESS", "PARTIAL", "FAILED"}


PROVIDER_LABELS = {
    "ECONTROLE": "eControle",
    "ACESSORIAS": "Acessórias",
    "SITTAX": "Sittax",
    "DOMINIO": "Domínio",
    "WATCHER_DOMINIO": "Watcher Domínio",
    "ECONET": "Econet",
    "WATCHER_G": "Watcher G:",
}


@dataclass
class PeriodContext:
    competencia: str
    period_id: int | None


def _iso_date(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _ie_display(value: str | None) -> str:
    if value is None or not value.strip():
        return "ISENTO"
    return value


def _regime_label_from_snapshot(snapshot: AcessoriasCompanySnapshot | None) -> str:
    if snapshot is None:
        return "Aguardando Acessorias"
    if snapshot.regime_mapping_status == "MAPPED" and snapshot.regime_canonical:
        try:
            return FISCAL_REGIME_LABELS[FiscalRegime(snapshot.regime_canonical)]
        except Exception:
            return snapshot.regime_canonical
    if snapshot.regime_mapping_status == "UNMAPPED":
        return "Regime nao mapeado"
    return "Aguardando Acessorias"


def _snapshot_map(db: Session, *, organization_id: int, company_ids: list[int]) -> dict[int, AcessoriasCompanySnapshot]:
    if not company_ids:
        return {}
    rows = db.scalars(
        select(AcessoriasCompanySnapshot)
        .where(
            AcessoriasCompanySnapshot.organization_id == organization_id,
            AcessoriasCompanySnapshot.company_id.in_(company_ids),
        )
        .order_by(AcessoriasCompanySnapshot.updated_at.desc(), AcessoriasCompanySnapshot.id.desc())
    ).all()
    result: dict[int, AcessoriasCompanySnapshot] = {}
    for row in rows:
        if row.company_id is not None and row.company_id not in result:
            result[row.company_id] = row
    return result


def _company_summary(company: ExternalCompany, snapshot: AcessoriasCompanySnapshot | None = None) -> CompanySummary:
    return CompanySummary(
        id=company.id,
        cnpj=company.cnpj,
        razao_social=company.razao_social,
        nome_fantasia=company.nome_fantasia,
        apelido_pasta=company.apelido_pasta,
        inscricao_estadual=company.inscricao_estadual,
        municipio=company.municipio,
        uf=company.uf,
        active=company.active,
        regime_label=_regime_label_from_snapshot(snapshot),
    )


def _parse_period(db: Session, organization_id: int, competencia: str | None) -> PeriodContext:
    base_query = select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id)
    if competencia:
        period = db.scalar(base_query.where(FiscalPeriod.competencia == competencia))
        return PeriodContext(competencia=competencia, period_id=period.id if period else None)

    latest_period = db.scalar(base_query.order_by(FiscalPeriod.year.desc(), FiscalPeriod.month.desc()))
    if latest_period is None:
        return PeriodContext(competencia="", period_id=None)
    return PeriodContext(competencia=latest_period.competencia, period_id=latest_period.id)


def list_companies(db: Session, *, organization_id: int, search: str | None) -> CompanyListResponse:
    query = select(ExternalCompany).where(
        ExternalCompany.organization_id == organization_id,
        ExternalCompany.active.is_(True),
    )
    if search:
        pattern = f"%{search.strip()}%"
        normalized = search.strip()
        query = query.where(
            or_(
                ExternalCompany.razao_social.ilike(pattern),
                ExternalCompany.nome_fantasia.ilike(pattern),
                ExternalCompany.apelido_pasta.ilike(pattern),
                ExternalCompany.cnpj.ilike(pattern),
                func.replace(func.replace(func.replace(ExternalCompany.cnpj, ".", ""), "/", ""), "-", "").ilike(
                    f"%{''.join(ch for ch in normalized if ch.isdigit())}%"
                ),
            )
        )

    companies = db.scalars(query.order_by(ExternalCompany.razao_social.asc(), ExternalCompany.id.asc())).all()
    snapshots = _snapshot_map(db, organization_id=organization_id, company_ids=[company.id for company in companies])
    return CompanyListResponse(items=[_company_summary(company, snapshots.get(company.id)) for company in companies])


def list_periods(db: Session, *, organization_id: int) -> PeriodListResponse:
    periods = db.scalars(
        select(FiscalPeriod)
        .where(FiscalPeriod.organization_id == organization_id)
        .order_by(FiscalPeriod.year.desc(), FiscalPeriod.month.desc())
    ).all()
    return PeriodListResponse(
        items=[
            PeriodItem(
                id=period.id,
                competencia=period.competencia,
                year=period.year,
                month=period.month,
                status=period.status,
            )
            for period in periods
        ]
    )


def get_dashboard(db: Session, *, organization_id: int, competencia: str | None) -> DashboardResponse:
    period = _parse_period(db, organization_id, competencia)
    companies_total = db.scalar(
        select(func.count()).select_from(ExternalCompany).where(
            ExternalCompany.organization_id == organization_id,
            ExternalCompany.active.is_(True),
        )
    ) or 0

    if period.period_id is None:
        return DashboardResponse(
            period=period.competencia,
            kpis=DashboardKpis(
                companies_total=companies_total,
                obligations_total=0,
                delivered_total=0,
                pending_total=0,
                divergences_total=0,
                evidences_total=0,
                installments_total=0,
            ),
            department_totals=[],
            status_totals=[],
            dctfweb=DashboardDctfwebSummary(),
            factor_r=DashboardFactorRSummary(),
        )

    obligation_rows = db.execute(
        select(
            FiscalObligationStatus.status,
            FiscalObligationStatus.responsible_department,
            func.count(FiscalObligationStatus.id),
        )
        .where(
            FiscalObligationStatus.organization_id == organization_id,
            FiscalObligationStatus.period_id == period.period_id,
        )
        .group_by(FiscalObligationStatus.status, FiscalObligationStatus.responsible_department)
    ).all()
    evidences_total = db.scalar(
        select(func.count()).select_from(FiscalEvidence).where(
            FiscalEvidence.organization_id == organization_id,
            FiscalEvidence.period_id == period.period_id,
        )
    ) or 0
    divergences_total = db.scalar(
        select(func.count()).select_from(FiscalAlert).where(
            FiscalAlert.organization_id == organization_id,
            FiscalAlert.period_id == period.period_id,
        )
    ) or 0
    installments_total = db.scalar(
        select(func.count()).select_from(FiscalInstallment).where(
            FiscalInstallment.organization_id == organization_id,
            FiscalInstallment.ultima_competencia_detectada == period.competencia,
        )
    ) or 0

    obligations_total = sum(row[2] for row in obligation_rows)
    delivered_total = sum(row[2] for row in obligation_rows if str(row[0]).upper() in {"ENTREGUE", "CONFIRMADO_API", "CONFIRMADO_ARQUIVO", "CONFIRMADO_ARQUIVO_ACESSORIAS"})
    pending_total = obligations_total - delivered_total

    department_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for status, department, total in obligation_rows:
        department_counts[str(department)] = department_counts.get(str(department), 0) + int(total)
        status_counts[str(status)] = status_counts.get(str(status), 0) + int(total)

    dctfweb_rows = db.scalars(select(DctfwebOriginAssessment).where(
        DctfwebOriginAssessment.organization_id == organization_id,
        DctfwebOriginAssessment.fiscal_period_id == period.period_id,
    )).all()
    factor_rows = db.scalars(select(FactorRAssessment).where(
        FactorRAssessment.organization_id == organization_id,
        FactorRAssessment.fiscal_period_id == period.period_id,
    )).all()

    return DashboardResponse(
        period=period.competencia,
        kpis=DashboardKpis(
            companies_total=companies_total,
            obligations_total=obligations_total,
            delivered_total=delivered_total,
            pending_total=pending_total,
            divergences_total=divergences_total,
            evidences_total=evidences_total,
            installments_total=installments_total,
        ),
        department_totals=[
            DashboardDepartmentSummary(department=department, total=total)
            for department, total in sorted(department_counts.items())
        ],
        status_totals=[
            DashboardStatusSummary(status=status, total=total)
            for status, total in sorted(status_counts.items())
        ],
        dctfweb=DashboardDctfwebSummary(
            evaluated=len(dctfweb_rows),
            dp=sum(row.expected_origin == "DP" for row in dctfweb_rows),
            fiscal=sum(row.expected_origin == "FISCAL" for row in dctfweb_rows),
            shared=sum(row.expected_origin == "COMPARTILHADO" for row in dctfweb_rows),
            undetermined=sum(row.expected_origin == "UNDETERMINED" for row in dctfweb_rows),
        ),
        factor_r=DashboardFactorRSummary(
            targets=len(factor_rows),
            effective=sum(row.applicability_status == "EFFECTIVE" for row in factor_rows),
            review=sum(row.applicability_status == "REVIEW" for row in factor_rows),
            calculated=sum(row.factor_r_estimated_dominio is not None for row in factor_rows),
            threshold_divergences=sum(row.reconciliation_status == "THRESHOLD_DIVERGENCE" for row in factor_rows),
            incomplete=sum(row.calculation_status != "COMPUTED" for row in factor_rows),
        ),
    )


def _cockpit_status(obligations_total: int, delivered_total: int, divergences_total: int) -> str:
    if divergences_total > 0:
        return "DIVERGENCIA"
    if obligations_total == 0:
        return "SEM_DADOS"
    if delivered_total == obligations_total:
        return "ENTREGUE"
    return "PENDENTE"


def _company_base_query(organization_id: int) -> Select[tuple[ExternalCompany]]:
    return select(ExternalCompany).where(
        ExternalCompany.organization_id == organization_id,
        ExternalCompany.active.is_(True),
    )


def get_cockpit(
    db: Session,
    *,
    organization_id: int,
    competencia: str | None,
    company_id: int | None,
    status: str | None,
    department: str | None,
    source: str | None,
) -> CockpitResponse:
    period = _parse_period(db, organization_id, competencia)
    companies = db.scalars(_company_base_query(organization_id).order_by(ExternalCompany.razao_social.asc())).all()

    if company_id is not None:
        companies = [company for company in companies if company.id == company_id]

    status_rows = []
    alert_rows = []
    if period.period_id is not None:
        status_query = select(FiscalObligationStatus).where(
            FiscalObligationStatus.organization_id == organization_id,
            FiscalObligationStatus.period_id == period.period_id,
        )
        if company_id is not None:
            status_query = status_query.where(FiscalObligationStatus.company_id == company_id)
        if status:
            status_query = status_query.where(FiscalObligationStatus.status == status)
        if department:
            status_query = status_query.where(FiscalObligationStatus.responsible_department == department)
        if source:
            status_query = status_query.where(FiscalObligationStatus.last_source == source)
        status_rows = db.scalars(status_query).all()

        alert_query = select(FiscalAlert).where(
            FiscalAlert.organization_id == organization_id,
            FiscalAlert.period_id == period.period_id,
        )
        if company_id is not None:
            alert_query = alert_query.where(FiscalAlert.company_id == company_id)
        alert_rows = db.scalars(alert_query).all()

    status_by_company: dict[int, list[FiscalObligationStatus]] = {}
    for row in status_rows:
        status_by_company.setdefault(row.company_id, []).append(row)

    alert_count_by_company: dict[int, int] = {}
    for row in alert_rows:
        if row.company_id is not None:
            alert_count_by_company[row.company_id] = alert_count_by_company.get(row.company_id, 0) + 1

    snapshots = _snapshot_map(db, organization_id=organization_id, company_ids=[company.id for company in companies])
    dctfweb_by_company = _dctfweb_by_company(db, organization_id=organization_id, period_id=period.period_id)
    factor_by_company = _factor_r_by_company(db, organization_id=organization_id, period_id=period.period_id)
    items: list[CockpitCompanyRow] = []
    for company in companies:
        company_statuses = status_by_company.get(company.id, [])
        obligations_total = len(company_statuses)
        delivered_total = sum(
            1
            for row in company_statuses
            if row.status in {"ENTREGUE", "CONFIRMADO_API", "CONFIRMADO_ARQUIVO", "CONFIRMADO_ARQUIVO_ACESSORIAS"}
        )
        pending_total = obligations_total - delivered_total
        divergences_total = alert_count_by_company.get(company.id, 0)
        overall_status = _cockpit_status(obligations_total, delivered_total, divergences_total)

        if status and not company_statuses and overall_status != status:
            continue

        first_status = company_statuses[0] if company_statuses else None
        dctfweb = dctfweb_by_company.get(company.id)
        factor = factor_by_company.get(company.id)
        items.append(
            CockpitCompanyRow(
                company_id=company.id,
                razao_social=company.razao_social,
                nome_fantasia=company.nome_fantasia,
                cnpj=company.cnpj,
                inscricao_estadual_display=_ie_display(company.inscricao_estadual),
                regime_label=_regime_label_from_snapshot(snapshots.get(company.id)),
                department=first_status.responsible_department if first_status else None,
                source=first_status.last_source if first_status else None,
                overall_status=overall_status,
                obligations_total=obligations_total,
                delivered_total=delivered_total,
                pending_total=pending_total,
                divergences_total=divergences_total,
                dctfweb_origin=dctfweb.expected_origin if dctfweb else None,
                dctfweb_department=dctfweb.expected_responsible_department if dctfweb else None,
                factor_r_status=factor.applicability_status if factor else None,
                factor_r_calculation_status=factor.calculation_status if factor else None,
                factor_r_reconciliation_status=factor.reconciliation_status if factor else None,
                factor_r_confidence=factor.fs12_confidence if factor else None,
                factor_r_estimated=str(factor.factor_r_estimated_dominio) if factor and factor.factor_r_estimated_dominio is not None else None,
                factor_r_observed=str(factor.factor_r_sittax_observed) if factor and factor.factor_r_sittax_observed is not None else None,
            )
        )

    return CockpitResponse(period=period.competencia, items=items)


def get_company_summary(db: Session, *, organization_id: int, company_id: int, competencia: str | None) -> CompanyDetailResponse | None:
    company = db.scalar(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization_id,
            ExternalCompany.id == company_id,
            ExternalCompany.active.is_(True),
        )
    )
    if company is None:
        return None

    period = _parse_period(db, organization_id, competencia)
    statuses: list[FiscalObligationStatus] = []
    evidence_total = 0
    divergence_total = 0
    installment_total = 0
    if period.period_id is not None:
        statuses = db.scalars(
            select(FiscalObligationStatus)
            .where(
                FiscalObligationStatus.organization_id == organization_id,
                FiscalObligationStatus.period_id == period.period_id,
                FiscalObligationStatus.company_id == company.id,
            )
            .order_by(FiscalObligationStatus.due_date.asc().nulls_last(), FiscalObligationStatus.id.asc())
        ).all()
        evidence_total = db.scalar(
            select(func.count()).select_from(FiscalEvidence).where(
                FiscalEvidence.organization_id == organization_id,
                FiscalEvidence.period_id == period.period_id,
                FiscalEvidence.company_id == company.id,
            )
        ) or 0
        divergence_total = db.scalar(
            select(func.count()).select_from(FiscalAlert).where(
                FiscalAlert.organization_id == organization_id,
                FiscalAlert.period_id == period.period_id,
                FiscalAlert.company_id == company.id,
            )
        ) or 0

    dctfweb = _dctfweb_by_company(db, organization_id=organization_id, period_id=period.period_id).get(company.id)
    factor = _factor_r_by_company(db, organization_id=organization_id, period_id=period.period_id).get(company.id)

    installment_total = db.scalar(
        select(func.count()).select_from(FiscalInstallment).where(
            FiscalInstallment.organization_id == organization_id,
            FiscalInstallment.company_id == company.id,
            FiscalInstallment.ultima_competencia_detectada == period.competencia,
        )
    ) or 0

    obligation_ids = [row.obligation_id for row in statuses]
    obligation_map = {}
    if obligation_ids:
        obligations = db.scalars(select(FiscalObligation).where(FiscalObligation.id.in_(obligation_ids))).all()
        obligation_map = {obligation.id: obligation for obligation in obligations}

    delivered_total = sum(
        1
        for row in statuses
        if row.status in {"ENTREGUE", "CONFIRMADO_API", "CONFIRMADO_ARQUIVO", "CONFIRMADO_ARQUIVO_ACESSORIAS"}
    )

    return CompanyDetailResponse(
        company=_company_summary(
            company,
            db.scalar(
                select(AcessoriasCompanySnapshot)
                .where(
                    AcessoriasCompanySnapshot.organization_id == organization_id,
                    AcessoriasCompanySnapshot.company_id == company.id,
                )
                .order_by(AcessoriasCompanySnapshot.updated_at.desc(), AcessoriasCompanySnapshot.id.desc())
            ),
        ),
        period=period.competencia,
        cnpj=company.cnpj,
        inscricao_estadual_display=_ie_display(company.inscricao_estadual),
        municipio_uf=" / ".join(part for part in [company.municipio, company.uf] if part) or "Nao informado",
        regime_label=_regime_label_from_snapshot(
            db.scalar(
                select(AcessoriasCompanySnapshot)
                .where(
                    AcessoriasCompanySnapshot.organization_id == organization_id,
                    AcessoriasCompanySnapshot.company_id == company.id,
                )
                .order_by(AcessoriasCompanySnapshot.updated_at.desc(), AcessoriasCompanySnapshot.id.desc())
            )
        ),
        kpis=CompanySummaryKpis(
            obligations_total=len(statuses),
            delivered_total=delivered_total,
            pending_total=len(statuses) - delivered_total,
            divergences_total=divergence_total,
            evidences_total=evidence_total,
            installments_total=installment_total,
        ),
        obligations=[
            CompanyObligationPreview(
                obligation_code=obligation_map.get(row.obligation_id).code if row.obligation_id in obligation_map else f"OBR-{row.obligation_id}",
                obligation_name=obligation_map.get(row.obligation_id).name if row.obligation_id in obligation_map else "Obrigacao",
                status=row.status,
                department=row.responsible_department,
                source=row.last_source,
                due_date=_iso_date(row.due_date),
                delivered_at=_iso_date(row.delivered_at),
            )
            for row in statuses
        ],
        evidences_preview=evidence_total,
        divergences_preview=divergence_total,
        dctfweb_origin=dctfweb.expected_origin if dctfweb else None,
        dctfweb_department=dctfweb.expected_responsible_department if dctfweb else None,
        factor_r_status=factor.applicability_status if factor else None,
        factor_r_calculation_status=factor.calculation_status if factor else None,
        factor_r_reconciliation_status=factor.reconciliation_status if factor else None,
        factor_r_confidence=factor.fs12_confidence if factor else None,
        factor_r_estimated=str(factor.factor_r_estimated_dominio) if factor and factor.factor_r_estimated_dominio is not None else None,
        factor_r_observed=str(factor.factor_r_sittax_observed) if factor and factor.factor_r_sittax_observed is not None else None,
        dominio_source_period=_previous_competence(period.competencia),
    )


def get_company_cnaes(db: Session, *, organization_id: int, company_id: int) -> CompanyCnaeListResponse:
    company = db.scalar(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization_id,
            ExternalCompany.id == company_id,
        )
    )
    if company is None:
        return CompanyCnaeListResponse(items=[])
    rows = db.scalars(
        select(CompanyCnae)
        .where(CompanyCnae.company_id == company_id)
        .order_by(CompanyCnae.active.desc(), CompanyCnae.is_primary.desc(), CompanyCnae.cnae.asc())
    ).all()
    return CompanyCnaeListResponse(
        items=[
            CompanyCnaeItemResponse(
                cnae=row.cnae,
                cnae_formatted=row.cnae_formatted,
                is_primary=row.is_primary,
                source=row.source,
                active=row.active,
                first_seen_at=_iso_date(row.first_seen_at) or "",
                last_seen_at=_iso_date(row.last_seen_at) or "",
                deactivated_at=_iso_date(row.deactivated_at),
            )
            for row in rows
        ]
    )


def get_company_factor_r_potential(db: Session, *, organization_id: int, company_id: int) -> FactorRPotentialResponse | None:
    company = db.scalar(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization_id,
            ExternalCompany.id == company_id,
        )
    )
    if company is None:
        return None
    result = compute_company_factor_r_potential(session=db, company_id=company_id)
    return FactorRPotentialResponse(
        company_id=result.company_id,
        status=result.status,
        factor_r_potential=result.factor_r_potential,
        cnaes_total=result.cnaes_total,
        cnaes_with_cache=result.cnaes_with_cache,
        positive_cnaes=result.positive_cnaes,
        negative_cnaes=result.negative_cnaes,
        missing_cnaes=result.missing_cnaes,
        annex_default=result.annex_default,
        annex_conditional=result.annex_conditional,
        factor_r_threshold=result.factor_r_threshold,
    )


def get_deliveries(db: Session, *, organization_id: int, competencia: str | None, company_id: int | None) -> DeliveryListResponse:
    period = _parse_period(db, organization_id, competencia)
    if period.period_id is None:
        return DeliveryListResponse(period=period.competencia, items=[])

    query = (
        select(FiscalObligationStatus, ExternalCompany, FiscalObligation)
        .join(ExternalCompany, ExternalCompany.id == FiscalObligationStatus.company_id)
        .join(FiscalObligation, FiscalObligation.id == FiscalObligationStatus.obligation_id)
        .where(
            FiscalObligationStatus.organization_id == organization_id,
            FiscalObligationStatus.period_id == period.period_id,
            ExternalCompany.organization_id == organization_id,
        )
        .order_by(ExternalCompany.razao_social.asc(), FiscalObligationStatus.due_date.asc().nulls_last())
    )
    if company_id is not None:
        query = query.where(FiscalObligationStatus.company_id == company_id)

    rows = db.execute(query).all()
    return DeliveryListResponse(
        period=period.competencia,
        items=[
            DeliveryItem(
                obligation_status_id=status.id,
                company_id=company.id,
                company_name=company.razao_social,
                cnpj=company.cnpj,
                obligation_code=obligation.code,
                obligation_name=obligation.name,
                status=status.status,
                department=status.responsible_department,
                source=status.last_source,
                due_date=_iso_date(status.due_date),
                delivered_at=_iso_date(status.delivered_at),
            )
            for status, company, obligation in rows
        ],
    )


def get_evidences(db: Session, *, organization_id: int, competencia: str | None, company_id: int | None) -> EvidenceListResponse:
    period = _parse_period(db, organization_id, competencia)
    query = (
        select(FiscalEvidence, ExternalCompany.razao_social)
        .join(ExternalCompany, ExternalCompany.id == FiscalEvidence.company_id, isouter=True)
        .where(FiscalEvidence.organization_id == organization_id)
        .order_by(FiscalEvidence.created_at.desc(), FiscalEvidence.id.desc())
    )
    if period.period_id is not None:
        query = query.where(FiscalEvidence.period_id == period.period_id)
    elif competencia:
        query = query.where(FiscalEvidence.competencia_detected == competencia)
    if company_id is not None:
        query = query.where(FiscalEvidence.company_id == company_id)

    rows = db.execute(query).all()
    return EvidenceListResponse(
        period=period.competencia,
        items=[
            EvidenceItem(
                id=evidence.id,
                company_id=evidence.company_id,
                company_name=company_name,
                source=evidence.source,
                source_type=evidence.source_type,
                file_name=evidence.file_name,
                detected_tax=evidence.detected_tax,
                detected_obligation=evidence.detected_obligation,
                competencia_detected=evidence.competencia_detected,
                status=evidence.status,
                created_at=_iso_date(evidence.created_at),
            )
            for evidence, company_name in rows
        ],
    )


def get_divergences(db: Session, *, organization_id: int, competencia: str | None, company_id: int | None) -> DivergenceListResponse:
    period = _parse_period(db, organization_id, competencia)
    query = (
        select(FiscalAlert, ExternalCompany.razao_social)
        .join(ExternalCompany, ExternalCompany.id == FiscalAlert.company_id, isouter=True)
        .where(FiscalAlert.organization_id == organization_id)
        .order_by(FiscalAlert.created_at.desc(), FiscalAlert.id.desc())
    )
    if period.period_id is not None:
        query = query.where(FiscalAlert.period_id == period.period_id)
    if company_id is not None:
        query = query.where(FiscalAlert.company_id == company_id)

    rows = db.execute(query).all()
    return DivergenceListResponse(
        period=period.competencia,
        items=[
            DivergenceItem(
                id=alert.id,
                company_id=alert.company_id,
                company_name=company_name,
                code=alert.code,
                title=alert.title,
                message=alert.message,
                severity=alert.severity,
                department=alert.department,
                source=alert.source,
                status=alert.status,
                created_at=_iso_date(alert.created_at),
            )
            for alert, company_name in rows
        ],
    )


def get_installments(db: Session, *, organization_id: int, competencia: str | None, company_id: int | None) -> InstallmentListResponse:
    period = _parse_period(db, organization_id, competencia)
    query = (
        select(FiscalInstallment, ExternalCompany.razao_social)
        .join(ExternalCompany, ExternalCompany.id == FiscalInstallment.company_id)
        .where(
            FiscalInstallment.organization_id == organization_id,
            ExternalCompany.organization_id == organization_id,
        )
        .order_by(FiscalInstallment.vencimento.asc().nulls_last(), FiscalInstallment.id.asc())
    )
    if period.competencia:
        query = query.where(FiscalInstallment.ultima_competencia_detectada == period.competencia)
    if company_id is not None:
        query = query.where(FiscalInstallment.company_id == company_id)

    rows = db.execute(query).all()
    return InstallmentListResponse(
        period=period.competencia,
        items=[
            InstallmentItem(
                id=installment.id,
                company_id=installment.company_id,
                company_name=company_name,
                tipo=installment.tipo,
                protocolo=installment.protocolo,
                quantidade_parcelas=installment.quantidade_parcelas,
                parcela_atual=installment.parcela_atual,
                valor_parcela=_float(installment.valor_parcela),
                vencimento=_iso_date(installment.vencimento),
                status=installment.status,
                source=installment.source,
                ultima_competencia_detectada=installment.ultima_competencia_detectada,
            )
            for installment, company_name in rows
        ],
    )


def get_integrations_health(db: Session, *, organization_id: int) -> IntegrationHealthResponse:
    settings = get_settings()
    account_rows = db.scalars(
        select(IntegrationAccount).where(IntegrationAccount.organization_id == organization_id)
    ).all()
    accounts_by_provider = {row.provider.upper(): row for row in account_rows}

    terminal_runs = db.scalars(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.organization_id == organization_id,
            IntegrationSyncRun.status.in_(TERMINAL_RUN_STATUSES),
        )
        .order_by(
            func.upper(IntegrationSyncRun.provider).asc(),
            IntegrationSyncRun.finished_at.desc().nulls_last(),
            IntegrationSyncRun.id.desc(),
        )
    ).all()
    latest_terminal_by_provider: dict[str, IntegrationSyncRun] = {}
    for run in terminal_runs:
        provider = run.provider.upper()
        if provider not in latest_terminal_by_provider:
            latest_terminal_by_provider[provider] = run

    active_runs = db.scalars(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.organization_id == organization_id,
            IntegrationSyncRun.status == "RUNNING",
        )
        .order_by(
            func.upper(IntegrationSyncRun.provider).asc(),
            IntegrationSyncRun.started_at.desc().nulls_last(),
            IntegrationSyncRun.id.desc(),
        )
    ).all()
    active_run_by_provider: dict[str, IntegrationSyncRun] = {}
    for run in active_runs:
        provider = run.provider.upper()
        if provider not in active_run_by_provider:
            active_run_by_provider[provider] = run

    items: list[IntegrationHealthItem] = []
    for provider, label in PROVIDER_LABELS.items():
        account = accounts_by_provider.get(provider)
        last_run = latest_terminal_by_provider.get(provider)
        active_run = active_run_by_provider.get(provider)
        stale_warning = None
        if active_run is not None and active_run.started_at is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)
            started_at = active_run.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if started_at < cutoff:
                stale_warning = (
                    f"Run RUNNING sem finalizacao ha mais de {STALE_RUN_MINUTES} minutos; "
                    "health usa o ultimo run terminal."
                )

        if provider == "ECONTROLE":
            note = "Espelho cadastral ativo no S5; leituras fiscais ainda sao read-only."
            status_value = account.status if account is not None else "CONFIGURAR"
        elif provider == "ACESSORIAS":
            configured = bool(settings.acessorias_api_token)
            note = "API oficial read-only do S6: empresas, regime e entregas, sem mutacoes externas."
            status_value = (
                last_run.status
                if last_run is not None
                else ("CONFIGURAR" if not configured else "NAO_INICIADA")
            )
        elif provider == "SITTAX":
            configured = bool(settings.sittax_email and settings.sittax_password)
            note = "Health local do S7.4 baseado em configuracao, ultimo run terminal e snapshots read-only."
            status_value = (
                last_run.status
                if last_run is not None
                else ("CONFIGURAR" if not configured else "NAO_INICIADA")
            )
        elif provider == "DOMINIO":
            note = "Health local baseado em imports e movimentos Domínio persistidos; nao acessa a UI Domínio."
            imports = db.scalar(
                select(func.count()).select_from(DominioPayrollImport).where(
                    DominioPayrollImport.organization_id == organization_id
                )
            ) or 0
            movements = db.scalar(
                select(func.count()).select_from(DominioPayrollCompanyMovement).where(
                    DominioPayrollCompanyMovement.organization_id == organization_id
                )
            ) or 0
            items.append(
                IntegrationHealthItem(
                    provider=provider,
                    label=label,
                    status=last_run.status if last_run is not None else "LOCAL_ONLY",
                    account_status=account.status if account is not None else "LOCAL_ONLY",
                    last_run_status=last_run.status if last_run is not None else None,
                    last_run_at=_iso_date(last_run.finished_at if last_run is not None else None),
                    processed_count=last_run.processed_count if last_run is not None else 0,
                    error_count=last_run.error_count if last_run is not None else 0,
                    note=note,
                    snapshot_counts={"imports": imports, "movements": movements},
                    active_run_status=active_run.status if active_run is not None else None,
                    active_run_started_at=_iso_date(active_run.started_at if active_run is not None else None),
                    stale_warning=stale_warning,
                )
            )
            continue
        elif provider == "WATCHER_DOMINIO":
            note = "Watcher local do diretório Domínio; valida manifest e encaminha somente relatórios canônicos ao importador."
            latest_detected_at = None
            latest_import_at = None
            if last_run is not None:
                metadata = last_run.run_metadata or {}
                latest_detected_at = metadata.get("detected_at")
                latest_import_at = metadata.get("imported_at")
            items.append(
                IntegrationHealthItem(
                    provider=provider,
                    label=label,
                    status=last_run.status if last_run is not None else "NAO_INICIADO",
                    account_status="LOCAL_ONLY",
                    last_run_status=last_run.status if last_run is not None else None,
                    last_run_at=_iso_date(last_run.finished_at if last_run is not None else None),
                    processed_count=last_run.processed_count if last_run is not None else 0,
                    error_count=last_run.error_count if last_run is not None else 0,
                    note=note,
                    active_run_status=active_run.status if active_run is not None else None,
                    active_run_started_at=_iso_date(active_run.started_at if active_run is not None else None),
                    stale_warning=stale_warning,
                    watcher_latest_detected_at=latest_detected_at,
                    watcher_latest_import_at=latest_import_at,
                )
            )
            continue
        elif provider == "ECONET":
            econet_snapshot = get_econet_assisted_session(settings).snapshot()
            cache_items = db.scalar(select(func.count()).select_from(EconetCnaeCache)) or 0
            cache_expired_items = db.scalar(
                select(func.count()).select_from(EconetCnaeCache).where(EconetCnaeCache.expires_at < datetime.now(timezone.utc))
            ) or 0
            cache_outdated_parser_items = db.scalar(
                select(func.count())
                .select_from(EconetCnaeCache)
                .where(EconetCnaeCache.parser_version != CURRENT_ECONET_PARSER_VERSION)
            ) or 0
            cache_last_refresh = db.scalar(select(func.max(EconetCnaeCache.retrieved_at)).select_from(EconetCnaeCache))
            catalog_active_items = db.scalar(select(func.count()).select_from(CompanyCnae).where(CompanyCnae.active.is_(True))) or 0
            catalog_unique_cnaes = db.scalar(
                select(func.count(func.distinct(CompanyCnae.cnae))).select_from(CompanyCnae).where(CompanyCnae.active.is_(True))
            ) or 0
            catalog_companies = db.scalar(
                select(func.count(func.distinct(CompanyCnae.company_id))).select_from(CompanyCnae).where(CompanyCnae.active.is_(True))
            ) or 0
            note_by_status = {
                "DISABLED": "Integracao desabilitada; health local sem chamadas externas.",
                "NOT_LOADED": "Aguardando login manual e importacao explicita da sessao.",
                "LOADED_UNVALIDATED": "Sessao carregada em memoria; probe explicito ainda nao executado.",
                "VALID": "Sessao assistida valida em memoria; health nao chama a Econet.",
                "EXPIRED": "Sessao expirada ou descartada; novo login manual e nova importacao sao necessarios.",
                "INVALID": "Sessao rejeitada pelo contrato local de seguranca.",
                "ERROR": "Ultimo probe encontrou falha tecnica; health permanece local.",
            }
            items.append(
                IntegrationHealthItem(
                    provider=provider,
                    label=label,
                    status=econet_snapshot["status"],
                    account_status="HABILITADA" if settings.econet_assisted_session_enabled else "DESABILITADA",
                    last_run_status=last_run.status if last_run is not None else None,
                    last_run_at=_iso_date(last_run.finished_at if last_run is not None else None),
                    processed_count=last_run.processed_count if last_run is not None else 0,
                    error_count=last_run.error_count if last_run is not None else 0,
                    note=note_by_status.get(econet_snapshot["status"], "Health local da sessao assistida da Econet."),
                    active_run_status=active_run.status if active_run is not None else None,
                    active_run_started_at=_iso_date(active_run.started_at if active_run is not None else None),
                    stale_warning=stale_warning,
                    session_status=econet_snapshot["status"],
                    session_loaded_at=econet_snapshot["loaded_at"],
                    session_validated_at=econet_snapshot["validated_at"],
                    session_expires_at=econet_snapshot["expires_at"],
                    cache_items=cache_items,
                    cache_expired_items=cache_expired_items,
                    cache_outdated_parser_items=cache_outdated_parser_items,
                    cache_last_refresh=_iso_date(cache_last_refresh),
                    snapshot_counts={
                        "catalog_active_items": catalog_active_items,
                        "catalog_unique_cnaes": catalog_unique_cnaes,
                        "catalog_companies": catalog_companies,
                    },
                )
            )
            continue
        else:
            note = "Nao iniciado neste stage S5.1."
            status_value = account.status if account is not None else "NAO_INICIADA"

        snapshot_counts = None
        if provider == "SITTAX":
            snapshot_counts = {
                "apuracoes": db.scalar(
                    select(func.count()).select_from(SittaxApuracaoSnapshot).where(
                        SittaxApuracaoSnapshot.organization_id == organization_id
                    )
                )
                or 0,
                "difal": db.scalar(
                    select(func.count()).select_from(SittaxDifalSnapshot).where(
                        SittaxDifalSnapshot.organization_id == organization_id
                    )
                )
                or 0,
                "documents": db.scalar(
                    select(func.count()).select_from(SittaxFiscalDocumentSnapshot).where(
                        SittaxFiscalDocumentSnapshot.organization_id == organization_id
                    )
                )
                or 0,
                "tasks": db.scalar(
                    select(func.count()).select_from(SittaxTaskSnapshot).where(
                        SittaxTaskSnapshot.organization_id == organization_id
                    )
                )
                or 0,
            }

        items.append(
            IntegrationHealthItem(
                provider=provider,
                label=label,
                status=status_value,
                account_status=(
                    account.status
                    if account is not None
                    else ("CONFIGURADO" if provider == "ACESSORIAS" and settings.acessorias_api_token else None)
                ),
                last_run_status=last_run.status if last_run is not None else None,
                last_run_at=_iso_date(last_run.finished_at if last_run is not None else None),
                processed_count=last_run.processed_count if last_run is not None else 0,
                error_count=last_run.error_count if last_run is not None else 0,
                note=note,
                snapshot_counts=snapshot_counts,
                active_run_status=active_run.status if active_run is not None else None,
                active_run_started_at=_iso_date(active_run.started_at if active_run is not None else None),
                stale_warning=stale_warning,
            )
        )

    return IntegrationHealthResponse(items=items)


def get_dominio_payroll_summary(
    db: Session, *, organization_id: int, source_period: str
) -> DominioPayrollSummaryResponse:
    source_date = _source_period_date(source_period)
    assessment_period = _next_competence(source_date)
    payroll_import = _canonical_dominio_import(db, organization_id=organization_id, source_period=source_period)
    if payroll_import is None:
        return DominioPayrollSummaryResponse(
            source_period=source_period,
            assessment_period=assessment_period,
            canonical_import_present=False,
        )
    movements = db.scalars(
        select(DominioPayrollCompanyMovement).where(DominioPayrollCompanyMovement.import_id == payroll_import.id)
    ).all()
    confidence_counts = {MONETARY_SUMMARY_COMPLETE: 0, MONETARY_SUMMARY_PARTIAL: 0, MONETARY_SUMMARY_INSUFFICIENT: 0}
    schema_v2 = 0
    unclassified = 0
    for movement in movements:
        summary = movement.rubrics_summary or {}
        if summary.get("schema_version") == 2:
            schema_v2 += 1
        confidence = summary.get("monetary_summary_confidence")
        if confidence in confidence_counts:
            confidence_counts[confidence] += 1
        monetary = summary.get("unclassified_monetary")
        if isinstance(monetary, dict) and monetary.get("rubric_count", 0):
            unclassified += 1
    return DominioPayrollSummaryResponse(
        source_period=source_period,
        assessment_period=assessment_period,
        canonical_import_present=True,
        selection_scope=payroll_import.selection_scope,
        import_status=payroll_import.status,
        companies=payroll_import.total_companies,
        matched=payroll_import.total_matched,
        unmatched=payroll_import.total_unmatched,
        warnings=payroll_import.total_warnings,
        schema_v2_movements=schema_v2,
        monetary_complete=confidence_counts[MONETARY_SUMMARY_COMPLETE],
        monetary_partial=confidence_counts[MONETARY_SUMMARY_PARTIAL],
        monetary_insufficient=confidence_counts[MONETARY_SUMMARY_INSUFFICIENT],
        unclassified_monetary_movements=unclassified,
    )


def get_dominio_payroll_company(
    db: Session, *, organization_id: int, company_id: int, source_period: str
) -> DominioPayrollCompanyResponse | None:
    _source_period_date(source_period)
    if not _company_exists(db, organization_id=organization_id, company_id=company_id):
        return None
    assessment_period = _next_competence(_source_period_date(source_period))
    payroll_import = _canonical_dominio_import(db, organization_id=organization_id, source_period=source_period)
    if payroll_import is None:
        return DominioPayrollCompanyResponse(
            company_id=company_id,
            source_period=source_period,
            assessment_period=assessment_period,
            coverage_status="REPORT_MISSING",
        )
    movement = db.scalar(
        select(DominioPayrollCompanyMovement).where(
            DominioPayrollCompanyMovement.import_id == payroll_import.id,
            DominioPayrollCompanyMovement.organization_id == organization_id,
            DominioPayrollCompanyMovement.external_company_id == company_id,
        )
    )
    if movement is None:
        return DominioPayrollCompanyResponse(
            company_id=company_id,
            source_period=source_period,
            assessment_period=assessment_period,
            coverage_status="CONFIRMED_NO_MOVEMENT",
        )
    summary = movement.rubrics_summary or {}
    categories = summary.get("monetary_categories") if isinstance(summary.get("monetary_categories"), dict) else {}
    def amount(category: str) -> str | None:
        payload = categories.get(category)
        return payload.get("amount") if isinstance(payload, dict) else None
    unclassified = summary.get("unclassified_monetary")
    warning_codes = sorted(
        str(item.get("code"))
        for item in (movement.warnings or [])
        if isinstance(item, dict) and item.get("code")
    )
    return DominioPayrollCompanyResponse(
        company_id=company_id,
        source_period=source_period,
        assessment_period=assessment_period,
        coverage_status="MOVEMENT_FOUND",
        match_status=movement.match_status,
        signals=DominioPayrollSignals(
            has_employee=movement.has_employee,
            has_pro_labore=movement.has_pro_labore,
            has_autonomous=movement.has_autonomous,
            has_inss=movement.has_inss,
            has_fgts=movement.has_fgts,
            has_termination=movement.has_termination,
            has_vacation=movement.has_vacation,
            has_leave=movement.has_leave,
        ),
        monetary_summary=DominioMonetarySummary(
            schema_version=summary.get("schema_version"),
            confidence=summary.get("monetary_summary_confidence"),
            employee_remuneration=amount("employee_remuneration"),
            pro_labore=amount("pro_labore"),
            autonomous=amount("autonomous"),
            thirteenth_salary=amount("thirteenth_salary"),
            employer_cpp_observed=amount("employer_cpp_observed"),
            fgts_observed=amount("fgts_observed"),
            unclassified_monetary_amount=unclassified.get("amount") if isinstance(unclassified, dict) else None,
        ),
        warning_codes=warning_codes,
    )


def get_dctfweb_origins(
    db: Session, *, organization_id: int, period: str, company_id: int | None, origin: str | None,
    department: str | None, coverage: str | None, limit: int, offset: int,
) -> DctfwebOriginListResponse:
    fiscal_period = _required_period(db, organization_id=organization_id, competencia=period)
    if company_id is not None:
        _require_company(db, organization_id=organization_id, company_id=company_id)
    query = select(DctfwebOriginAssessment).where(
        DctfwebOriginAssessment.organization_id == organization_id,
        DctfwebOriginAssessment.fiscal_period_id == fiscal_period.id,
    )
    if company_id is not None:
        query = query.where(DctfwebOriginAssessment.external_company_id == company_id)
    if origin:
        query = query.where(DctfwebOriginAssessment.expected_origin == origin)
    if department:
        query = query.where(DctfwebOriginAssessment.expected_responsible_department == department)
    if coverage:
        query = query.where(DctfwebOriginAssessment.dp_coverage_status == coverage)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(DctfwebOriginAssessment.external_company_id, DctfwebOriginAssessment.id).offset(offset).limit(limit)).all()
    return DctfwebOriginListResponse(period=period, total=total, items=[_dctfweb_item(row) for row in rows])


def get_dctfweb_origin_detail(
    db: Session, *, organization_id: int, company_id: int, period: str
) -> DctfwebOriginItem | None:
    fiscal_period = _required_period(db, organization_id=organization_id, competencia=period)
    _require_company(db, organization_id=organization_id, company_id=company_id)
    row = db.scalar(select(DctfwebOriginAssessment).where(
        DctfwebOriginAssessment.organization_id == organization_id,
        DctfwebOriginAssessment.external_company_id == company_id,
        DctfwebOriginAssessment.fiscal_period_id == fiscal_period.id,
    ))
    return _dctfweb_item(row) if row else None


def get_dctfweb_summary(db: Session, *, organization_id: int, period: str) -> DctfwebSummaryResponse:
    rows = get_dctfweb_origins(
        db, organization_id=organization_id, period=period, company_id=None, origin=None, department=None,
        coverage=None, limit=500, offset=0,
    ).items
    return DctfwebSummaryResponse(
        period=period,
        evaluated=len(rows),
        dp=sum(row.expected_origin == "DP" for row in rows),
        fiscal=sum(row.expected_origin == "FISCAL" for row in rows),
        shared=sum(row.expected_origin == "COMPARTILHADO" for row in rows),
        undetermined=sum(row.expected_origin == "UNDETERMINED" for row in rows),
        dominio_report_missing=sum(row.dominio_coverage == "REPORT_MISSING" for row in rows),
        reinf_signal_companies=sum(row.reinf_signal_present for row in rows),
        mit_signal_companies=sum(row.mit_signal_present for row in rows),
        dctfweb_observed=sum(row.dctfweb_observed for row in rows),
    )


def get_factor_r_assessments(
    db: Session, *, organization_id: int, period: str, company_id: int | None, applicability: str | None,
    calculation_status: str | None, reconciliation_status: str | None, confidence: str | None,
    threshold_side: str | None, limit: int, offset: int,
) -> FactorRListResponse:
    fiscal_period = _required_period(db, organization_id=organization_id, competencia=period)
    if company_id is not None:
        _require_company(db, organization_id=organization_id, company_id=company_id)
    query = select(FactorRAssessment).where(
        FactorRAssessment.organization_id == organization_id,
        FactorRAssessment.fiscal_period_id == fiscal_period.id,
    )
    filters = (
        (company_id, FactorRAssessment.external_company_id), (applicability, FactorRAssessment.applicability_status),
        (calculation_status, FactorRAssessment.calculation_status), (reconciliation_status, FactorRAssessment.reconciliation_status),
        (confidence, FactorRAssessment.fs12_confidence), (threshold_side, FactorRAssessment.estimated_threshold_side),
    )
    for value, column in filters:
        if value is not None:
            query = query.where(column == value)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(FactorRAssessment.external_company_id, FactorRAssessment.id).offset(offset).limit(limit)).all()
    return FactorRListResponse(period=period, total=total, items=[_factor_r_item(row) for row in rows])


def get_factor_r_detail(db: Session, *, organization_id: int, company_id: int, period: str) -> FactorRDetailResponse | None:
    fiscal_period = _required_period(db, organization_id=organization_id, competencia=period)
    _require_company(db, organization_id=organization_id, company_id=company_id)
    row = db.scalar(select(FactorRAssessment).where(
        FactorRAssessment.organization_id == organization_id,
        FactorRAssessment.external_company_id == company_id,
        FactorRAssessment.fiscal_period_id == fiscal_period.id,
    ))
    if row is None:
        return None
    item = _factor_r_item(row)
    return FactorRDetailResponse(
        **item.model_dump(),
        payroll_window_start=_iso_date(row.payroll_window_start) or "",
        payroll_window_end=_iso_date(row.payroll_window_end) or "",
        payroll_months_expected=row.payroll_months_expected,
        payroll_months_covered=row.payroll_months_covered,
        payroll_months_with_movement=row.payroll_months_with_movement,
        payroll_months_confirmed_zero=row.payroll_months_confirmed_zero,
        payroll_months_missing=row.payroll_months_missing,
        fs12_dominio_estimate=row.fs12_dominio_estimate,
        fs12_breakdown={str(key): str(value) for key, value in (row.fs12_breakdown or {}).items()},
        rbt12_value=row.rbt12_value,
        rbt12_source=row.rbt12_source,
        rbt12_confidence=row.rbt12_confidence,
        estimated_annex=row.estimated_annex,
        sittax_observed_annexes=list(row.sittax_observed_annexes or []),
    )


def get_factor_r_summary(db: Session, *, organization_id: int, period: str) -> FactorRSummaryResponse:
    fiscal_period = _required_period(db, organization_id=organization_id, competencia=period)
    rows = db.scalars(select(FactorRAssessment).where(
        FactorRAssessment.organization_id == organization_id,
        FactorRAssessment.fiscal_period_id == fiscal_period.id,
    )).all()
    active_companies = db.scalar(select(func.count()).select_from(ExternalCompany).where(
        ExternalCompany.organization_id == organization_id, ExternalCompany.active.is_(True)
    )) or 0
    reasons = [set(row.reason_codes or []) for row in rows]
    return FactorRSummaryResponse(
        period=period, target_companies=len(rows),
        potential=sum(row.applicability_status == "POTENTIAL" for row in rows),
        effective=sum(row.applicability_status == "EFFECTIVE" for row in rows),
        review=sum(row.applicability_status == "REVIEW" for row in rows),
        not_applicable=max(0, active_companies - len(rows)),
        full_payroll_coverage=sum(row.payroll_months_missing == 0 for row in rows),
        partial_payroll_coverage=sum(row.payroll_months_missing > 0 for row in rows),
        fs12_estimated=sum(row.fs12_dominio_estimate is not None for row in rows),
        fs12_high=sum(row.fs12_confidence == "HIGH" for row in rows),
        fs12_medium=sum(row.fs12_confidence == "MEDIUM" for row in rows),
        fs12_low=sum(row.fs12_confidence == "LOW" for row in rows),
        fs12_insufficient=sum(row.fs12_confidence == "INSUFFICIENT" for row in rows),
        rbt12_available=sum(row.rbt12_value is not None for row in rows),
        factor_r_calculated=sum(row.factor_r_estimated_dominio is not None for row in rows),
        above_or_equal_28=sum(row.estimated_threshold_side == "ABOVE_OR_EQUAL_28" for row in rows),
        below_28=sum(row.estimated_threshold_side == "BELOW_28" for row in rows),
        sittax_factor_observed=sum(row.factor_r_sittax_observed is not None for row in rows),
        threshold_matches=sum(row.reconciliation_status == "MATCH" for row in rows),
        threshold_divergences=sum(row.reconciliation_status == "THRESHOLD_DIVERGENCE" for row in rows),
        near_threshold_low_confidence=sum("NEAR_THRESHOLD_LOW_CONFIDENCE" in value for value in reasons),
        annex_reviews=sum(row.reconciliation_status == "ANNEX_REVIEW" for row in rows),
        thirteenth_coverage_limitation=sum("THIRTEENTH_SALARY_COVERAGE_UNVERIFIED" in value for value in reasons),
        unclassified_relevant_limitation=sum(
            "UNCLASSIFIED_MONETARY_RELEVANT" in value or "UNCLASSIFIED_MONETARY_UNKNOWN" in value for value in reasons
        ),
    )


def _dctfweb_item(row: DctfwebOriginAssessment) -> DctfwebOriginItem:
    return DctfwebOriginItem(
        company_id=row.external_company_id, expected_origin=row.expected_origin,
        expected_department=row.expected_responsible_department, dominio_coverage=row.dp_coverage_status,
        dp_signal_present=row.dp_signal_present, reinf_signal_present=row.reinf_signal_present,
        mit_signal_present=row.mit_signal_present, fiscal_signal_present=row.fiscal_signal_present,
        dctfweb_observed=row.dctfweb_observed, classification_confidence=row.classification_confidence,
        reason_codes=list(row.reason_codes or []), evaluated_at=_iso_date(row.evaluated_at) or "",
    )


def _factor_r_item(row: FactorRAssessment) -> FactorRItem:
    return FactorRItem(
        company_id=row.external_company_id, applicability_status=row.applicability_status,
        calculation_status=row.calculation_status, fs12_confidence=row.fs12_confidence,
        factor_r_estimated=row.factor_r_estimated_dominio, factor_r_sittax_observed=row.factor_r_sittax_observed,
        factor_r_delta=row.factor_r_delta, threshold_side=row.estimated_threshold_side,
        reconciliation_status=row.reconciliation_status, reason_codes=list(row.reason_codes or []),
        evaluated_at=_iso_date(row.evaluated_at) or "",
    )


def _source_period_date(value: str) -> date:
    try:
        year, month = value.split("-", maxsplit=1)
        return date(int(year), int(month), 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("Competence must be in YYYY-MM format.") from exc


def _next_competence(value: date) -> str:
    year, month = (value.year + 1, 1) if value.month == 12 else (value.year, value.month + 1)
    return f"{year:04d}-{month:02d}"


def _previous_competence(value: str) -> str:
    source_date = _source_period_date(value)
    year, month = (source_date.year - 1, 12) if source_date.month == 1 else (source_date.year, source_date.month - 1)
    return f"{year:04d}-{month:02d}"


def _dctfweb_by_company(
    db: Session, *, organization_id: int, period_id: int | None
) -> dict[int, DctfwebOriginAssessment]:
    if period_id is None:
        return {}
    return {
        row.external_company_id: row
        for row in db.scalars(select(DctfwebOriginAssessment).where(
            DctfwebOriginAssessment.organization_id == organization_id,
            DctfwebOriginAssessment.fiscal_period_id == period_id,
        )).all()
    }


def _factor_r_by_company(db: Session, *, organization_id: int, period_id: int | None) -> dict[int, FactorRAssessment]:
    if period_id is None:
        return {}
    return {
        row.external_company_id: row
        for row in db.scalars(select(FactorRAssessment).where(
            FactorRAssessment.organization_id == organization_id,
            FactorRAssessment.fiscal_period_id == period_id,
        )).all()
    }


def _canonical_dominio_import(db: Session, *, organization_id: int, source_period: str) -> DominioPayrollImport | None:
    rows = db.scalars(select(DominioPayrollImport).where(
        DominioPayrollImport.organization_id == organization_id,
        DominioPayrollImport.selection_scope == "ACTIVE_COMPANIES",
        DominioPayrollImport.status.not_in(("FAILED", "PROCESSING")),
    ).order_by(DominioPayrollImport.imported_at.desc().nulls_last(), DominioPayrollImport.id.desc())).all()
    return next((row for row in rows if source_period in (row.source_competences or [])), None)


def _company_exists(db: Session, *, organization_id: int, company_id: int) -> bool:
    return db.scalar(select(ExternalCompany.id).where(
        ExternalCompany.organization_id == organization_id, ExternalCompany.id == company_id
    )) is not None


def _require_company(db: Session, *, organization_id: int, company_id: int) -> None:
    if not _company_exists(db, organization_id=organization_id, company_id=company_id):
        raise LookupError("Company not found.")


def _required_period(db: Session, *, organization_id: int, competencia: str) -> FiscalPeriod:
    _source_period_date(competencia)
    period = db.scalar(select(FiscalPeriod).where(
        FiscalPeriod.organization_id == organization_id, FiscalPeriod.competencia == competencia
    ))
    if period is None:
        raise LookupError("Fiscal period not found.")
    return period
