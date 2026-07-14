from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_auth_context, require_roles
from backend.app.db.session import get_db
from backend.app.schemas.cockpit import CockpitResponse
from backend.app.schemas.company import CompanyDetailResponse, CompanyListResponse
from backend.app.schemas.dashboard import DashboardResponse
from backend.app.schemas.delivery import DeliveryListResponse
from backend.app.schemas.divergence import DivergenceListResponse
from backend.app.schemas.evidence import EvidenceListResponse
from backend.app.schemas.installment import InstallmentListResponse
from backend.app.schemas.integration import IntegrationHealthResponse
from backend.app.schemas.period import PeriodListResponse
from backend.app.services.auth import AuthContext, ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.app.services import lumen_read_model


router = APIRouter(prefix="/lumen", tags=["lumen"])


def _authorized_context(
    _: object = Depends(require_roles(ROLE_VIEW, ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


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
