from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_auth_context, require_roles
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.organization import Organization
from backend.app.schemas.cockpit import CockpitResponse
from backend.app.schemas.company import CompanyDetailResponse, CompanyListResponse
from backend.app.schemas.dashboard import DashboardResponse
from backend.app.schemas.delivery import DeliveryListResponse
from backend.app.schemas.divergence import DivergenceListResponse
from backend.app.schemas.econet import CompanyCnaeListResponse, FactorRPotentialResponse
from backend.app.schemas.evidence import EvidenceListResponse
from backend.app.schemas.installment import InstallmentListResponse
from backend.app.schemas.integration import IntegrationHealthResponse
from backend.app.schemas.lumen_s9 import (
    DctfwebOriginItem,
    DctfwebOriginListResponse,
    DctfwebSummaryResponse,
    DominioPayrollCompanyResponse,
    DominioPayrollSummaryResponse,
    FactorRDetailResponse,
    FactorRListResponse,
    FactorRSummaryResponse,
    ReconcileRequest,
    ReconcileResponse,
)
from backend.app.schemas.period import PeriodListResponse
from backend.app.schemas.watcher import WatcherEventIngestRequest, WatcherEventIngestResponse
from backend.app.services.auth import AuthContext, ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.app.services import lumen_read_model
from backend.app.services.dctfweb_origins import reconcile_dctfweb_period
from backend.app.services.factor_r_reconciliation import reconcile_factor_r_period
from backend.app.services.watcher_ingest import WatcherIngestError, ingest_watcher_event


router = APIRouter(prefix="/lumen", tags=["lumen"])


def _authorized_context(
    _: object = Depends(require_roles(ROLE_VIEW, ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


def _admin_context(
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


def _read_error(exc: ValueError | LookupError) -> HTTPException:
    code = status.HTTP_422_UNPROCESSABLE_ENTITY if isinstance(exc, ValueError) else status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=code, detail=str(exc))


def _watcher_agent_organization(
    x_lumen_agent_token: str | None = Header(default=None, alias="X-Lumen-Agent-Token"),
    db: Session = Depends(get_db),
) -> Organization:
    settings = get_settings()
    configured_token = settings.lumen_watcher_agent_token
    configured_org_slug = settings.lumen_watcher_agent_org_slug
    if not configured_token or not configured_org_slug:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Watcher ingest is not configured.")
    if not x_lumen_agent_token or not hmac.compare_digest(x_lumen_agent_token, configured_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Watcher authentication failed.")
    organization = db.scalar(select(Organization).where(Organization.slug == configured_org_slug))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Watcher ingest is unavailable.")
    return organization


@router.get("/companies", response_model=CompanyListResponse)
def companies(
    search: str = Query(default=""),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    return lumen_read_model.list_companies(db, organization_id=context.organization.id, search=search)


@router.get("/periods", response_model=PeriodListResponse)
def periods(
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> PeriodListResponse:
    return lumen_read_model.list_periods(db, organization_id=context.organization.id)


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    period: str | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    return lumen_read_model.get_dashboard(db, organization_id=context.organization.id, competencia=period)


@router.get("/cockpit", response_model=CockpitResponse)
def cockpit(
    period: str | None = Query(default=None),
    companyId: int | None = Query(default=None),
    status: str | None = Query(default=None),
    department: str | None = Query(default=None),
    source: str | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> CockpitResponse:
    return lumen_read_model.get_cockpit(
        db,
        organization_id=context.organization.id,
        competencia=period,
        company_id=companyId,
        status=status,
        department=department,
        source=source,
    )


@router.get("/companies/{company_id}/summary", response_model=CompanyDetailResponse)
def company_summary(
    company_id: int,
    period: str | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> CompanyDetailResponse:
    response = lumen_read_model.get_company_summary(
        db,
        organization_id=context.organization.id,
        company_id=company_id,
        competencia=period,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return response


@router.get("/companies/{company_id}/cnaes", response_model=CompanyCnaeListResponse)
def company_cnaes(
    company_id: int,
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> CompanyCnaeListResponse:
    return lumen_read_model.get_company_cnaes(db, organization_id=context.organization.id, company_id=company_id)


@router.get("/companies/{company_id}/factor-r-potential", response_model=FactorRPotentialResponse)
def company_factor_r_potential(
    company_id: int,
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> FactorRPotentialResponse:
    response = lumen_read_model.get_company_factor_r_potential(db, organization_id=context.organization.id, company_id=company_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return response


@router.get("/deliveries", response_model=DeliveryListResponse)
def deliveries(
    period: str | None = Query(default=None),
    companyId: int | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DeliveryListResponse:
    return lumen_read_model.get_deliveries(
        db,
        organization_id=context.organization.id,
        competencia=period,
        company_id=companyId,
    )


@router.get("/evidences", response_model=EvidenceListResponse)
def evidences(
    period: str | None = Query(default=None),
    companyId: int | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> EvidenceListResponse:
    return lumen_read_model.get_evidences(
        db,
        organization_id=context.organization.id,
        competencia=period,
        company_id=companyId,
    )


@router.post("/evidences/watcher-event", response_model=WatcherEventIngestResponse)
def ingest_watcher_event_endpoint(
    body: WatcherEventIngestRequest,
    organization: Organization = Depends(_watcher_agent_organization),
    db: Session = Depends(get_db),
) -> WatcherEventIngestResponse:
    try:
        result = ingest_watcher_event(db, organization=organization, payload=body)
        db.commit()
    except WatcherIngestError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid watcher event.") from exc
    return WatcherEventIngestResponse(
        event_id=result.event.id,
        evidence_id=result.evidence.id if result.evidence is not None else None,
        event_created=result.event_created,
        evidence_created=result.evidence_created,
        company_resolution=result.company_resolution.value,
        period_resolution=result.period_resolution.value,
        status=result.event.status,
    )


@router.get("/divergences", response_model=DivergenceListResponse)
def divergences(
    period: str | None = Query(default=None),
    companyId: int | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DivergenceListResponse:
    return lumen_read_model.get_divergences(
        db,
        organization_id=context.organization.id,
        competencia=period,
        company_id=companyId,
    )


@router.get("/installments", response_model=InstallmentListResponse)
def installments(
    period: str | None = Query(default=None),
    companyId: int | None = Query(default=None),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> InstallmentListResponse:
    return lumen_read_model.get_installments(
        db,
        organization_id=context.organization.id,
        competencia=period,
        company_id=companyId,
    )


@router.get("/integrations/health", response_model=IntegrationHealthResponse)
def integrations_health(
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> IntegrationHealthResponse:
    return lumen_read_model.get_integrations_health(db, organization_id=context.organization.id)


@router.get("/dominio/payroll/summary", response_model=DominioPayrollSummaryResponse)
def dominio_payroll_summary(
    sourcePeriod: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DominioPayrollSummaryResponse:
    try:
        return lumen_read_model.get_dominio_payroll_summary(
            db, organization_id=context.organization.id, source_period=sourcePeriod
        )
    except ValueError as exc:
        raise _read_error(exc) from exc


@router.get("/companies/{company_id}/dominio/payroll", response_model=DominioPayrollCompanyResponse)
def dominio_payroll_company(
    company_id: int,
    sourcePeriod: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DominioPayrollCompanyResponse:
    try:
        response = lumen_read_model.get_dominio_payroll_company(
            db, organization_id=context.organization.id, company_id=company_id, source_period=sourcePeriod
        )
    except ValueError as exc:
        raise _read_error(exc) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return response


@router.get("/dctfweb/origins", response_model=DctfwebOriginListResponse)
def dctfweb_origins(
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    companyId: int | None = None,
    origin: str | None = None,
    department: str | None = None,
    coverage: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DctfwebOriginListResponse:
    try:
        return lumen_read_model.get_dctfweb_origins(
            db, organization_id=context.organization.id, period=period, company_id=companyId, origin=origin,
            department=department, coverage=coverage, limit=limit, offset=offset,
        )
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc


@router.get("/companies/{company_id}/dctfweb-origin", response_model=DctfwebOriginItem)
def dctfweb_origin_detail(
    company_id: int,
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DctfwebOriginItem:
    try:
        response = lumen_read_model.get_dctfweb_origin_detail(
            db, organization_id=context.organization.id, company_id=company_id, period=period
        )
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DCTFWeb origin assessment not found.")
    return response


@router.get("/dctfweb/summary", response_model=DctfwebSummaryResponse)
def dctfweb_summary(
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> DctfwebSummaryResponse:
    try:
        return lumen_read_model.get_dctfweb_summary(db, organization_id=context.organization.id, period=period)
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc


@router.get("/factor-r", response_model=FactorRListResponse)
def factor_r_assessments(
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    companyId: int | None = None,
    applicability: str | None = None,
    calculationStatus: str | None = None,
    reconciliationStatus: str | None = None,
    confidence: str | None = None,
    thresholdSide: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> FactorRListResponse:
    try:
        return lumen_read_model.get_factor_r_assessments(
            db, organization_id=context.organization.id, period=period, company_id=companyId,
            applicability=applicability, calculation_status=calculationStatus,
            reconciliation_status=reconciliationStatus, confidence=confidence, threshold_side=thresholdSide,
            limit=limit, offset=offset,
        )
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc


@router.get("/factor-r/summary", response_model=FactorRSummaryResponse)
def factor_r_summary(
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> FactorRSummaryResponse:
    try:
        return lumen_read_model.get_factor_r_summary(db, organization_id=context.organization.id, period=period)
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc


@router.get("/companies/{company_id}/factor-r", response_model=FactorRDetailResponse)
def factor_r_detail(
    company_id: int,
    period: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> FactorRDetailResponse:
    try:
        response = lumen_read_model.get_factor_r_detail(
            db, organization_id=context.organization.id, company_id=company_id, period=period
        )
    except (ValueError, LookupError) as exc:
        raise _read_error(exc) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factor R assessment not found.")
    return response


@router.post("/dctfweb/reconcile", response_model=ReconcileResponse)
def reconcile_dctfweb(
    body: ReconcileRequest,
    context: AuthContext = Depends(_admin_context),
    db: Session = Depends(get_db),
) -> ReconcileResponse:
    if body.company_id is not None:
        try:
            lumen_read_model._require_company(db, organization_id=context.organization.id, company_id=body.company_id)
        except LookupError as exc:
            raise _read_error(exc) from exc
    try:
        summary = reconcile_dctfweb_period(
            db, context.organization, body.period, external_company_id=body.company_id, dry_run=body.dry_run
        )
    except ValueError as exc:
        raise _read_error(exc) from exc
    return ReconcileResponse(summary=summary.to_dict())


@router.post("/factor-r/reconcile", response_model=ReconcileResponse)
def reconcile_factor_r(
    body: ReconcileRequest,
    context: AuthContext = Depends(_admin_context),
    db: Session = Depends(get_db),
) -> ReconcileResponse:
    if body.company_id is not None:
        try:
            lumen_read_model._require_company(db, organization_id=context.organization.id, company_id=body.company_id)
        except LookupError as exc:
            raise _read_error(exc) from exc
    try:
        summary = reconcile_factor_r_period(
            db, context.organization, body.period, company_id=body.company_id, dry_run=body.dry_run
        )
    except ValueError as exc:
        raise _read_error(exc) from exc
    return ReconcileResponse(summary=summary.to_dict())
