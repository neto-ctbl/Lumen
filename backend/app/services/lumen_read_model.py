from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_alert import FiscalAlert
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_installment import FiscalInstallment
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_account import IntegrationAccount
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.schemas.cockpit import CockpitCompanyRow, CockpitResponse
from backend.app.schemas.company import (
    CompanyDetailResponse,
    CompanyListResponse,
    CompanyObligationPreview,
    CompanySummary,
    CompanySummaryKpis,
)
from backend.app.schemas.dashboard import (
    DashboardDepartmentSummary,
    DashboardKpis,
    DashboardResponse,
    DashboardStatusSummary,
)
from backend.app.schemas.delivery import DeliveryItem, DeliveryListResponse
from backend.app.schemas.divergence import DivergenceItem, DivergenceListResponse
from backend.app.schemas.evidence import EvidenceItem, EvidenceListResponse
from backend.app.schemas.installment import InstallmentItem, InstallmentListResponse
from backend.app.schemas.integration import IntegrationHealthItem, IntegrationHealthResponse
from backend.app.schemas.period import PeriodItem, PeriodListResponse


PROVIDER_LABELS = {
    "ECONTROLE": "eControle",
    "ACESSORIAS": "Acessorias",
    "SITTAX": "Sittax",
    "DOMINIO": "Dominio",
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


def _regime_label(_: ExternalCompany) -> str:
    return "Aguardando Acessorias"


def _company_summary(company: ExternalCompany) -> CompanySummary:
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
        regime_label=_regime_label(company),
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
    return CompanyListResponse(items=[_company_summary(company) for company in companies])


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
        items.append(
            CockpitCompanyRow(
                company_id=company.id,
                razao_social=company.razao_social,
                nome_fantasia=company.nome_fantasia,
                cnpj=company.cnpj,
                inscricao_estadual_display=_ie_display(company.inscricao_estadual),
                regime_label=_regime_label(company),
                department=first_status.responsible_department if first_status else None,
                source=first_status.last_source if first_status else None,
                overall_status=overall_status,
                obligations_total=obligations_total,
                delivered_total=delivered_total,
                pending_total=pending_total,
                divergences_total=divergences_total,
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
        company=_company_summary(company),
        period=period.competencia,
        cnpj=company.cnpj,
        inscricao_estadual_display=_ie_display(company.inscricao_estadual),
        municipio_uf=" / ".join(part for part in [company.municipio, company.uf] if part) or "Nao informado",
        regime_label=_regime_label(company),
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
    account_rows = db.scalars(
        select(IntegrationAccount).where(IntegrationAccount.organization_id == organization_id)
    ).all()
    accounts_by_provider = {row.provider.upper(): row for row in account_rows}

    run_rows = db.execute(
        select(
            IntegrationSyncRun.provider,
            func.max(IntegrationSyncRun.finished_at),
        )
        .where(IntegrationSyncRun.organization_id == organization_id)
        .group_by(IntegrationSyncRun.provider)
    ).all()
    latest_run_lookup = {str(provider).upper(): finished_at for provider, finished_at in run_rows}

    items: list[IntegrationHealthItem] = []
    for provider, label in PROVIDER_LABELS.items():
        account = accounts_by_provider.get(provider)
        finished_at = latest_run_lookup.get(provider)
        last_run = None
        if finished_at is not None:
            last_run = db.scalar(
                select(IntegrationSyncRun)
                .where(
                    IntegrationSyncRun.organization_id == organization_id,
                    func.upper(IntegrationSyncRun.provider) == provider,
                    IntegrationSyncRun.finished_at == finished_at,
                )
                .order_by(IntegrationSyncRun.id.desc())
            )

        if provider == "ECONTROLE":
            note = "Espelho cadastral ativo no S5; leituras fiscais ainda sao read-only."
            status_value = account.status if account is not None else "CONFIGURAR"
        else:
            note = "Nao iniciado neste stage S5.1."
            status_value = account.status if account is not None else "NAO_INICIADA"

        items.append(
            IntegrationHealthItem(
                provider=provider,
                label=label,
                status=status_value,
                account_status=account.status if account is not None else None,
                last_run_status=last_run.status if last_run is not None else None,
                last_run_at=_iso_date(last_run.finished_at if last_run is not None else None),
                processed_count=last_run.processed_count if last_run is not None else 0,
                error_count=last_run.error_count if last_run is not None else 0,
                note=note,
            )
        )

    return IntegrationHealthResponse(items=items)
