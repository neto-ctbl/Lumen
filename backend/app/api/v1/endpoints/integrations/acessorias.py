from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_auth_context, require_roles
from backend.app.db.session import get_db
from backend.app.models.external_company import ExternalCompany
from backend.app.schemas.acessorias import AcessoriasSyncRequest, AcessoriasSyncResponse
from backend.app.services.auth import AuthContext, ROLE_ADMIN, ROLE_DEV
from backend.app.services.integrations.acessorias.client import (
    AcessoriasAuthenticationError,
    AcessoriasConfigurationError,
    AcessoriasNotFoundError,
    AcessoriasRateLimitError,
    AcessoriasResponseError,
    AcessoriasTransportError,
)
from backend.app.services.integrations.acessorias.sync import audit_manual_sync, sync_acessorias_period


router = APIRouter(prefix="/integrations/acessorias", tags=["integrations"])


def _authorized_context(
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


@router.post("/sync", response_model=AcessoriasSyncResponse)
def sync_acessorias(
    body: AcessoriasSyncRequest,
    context: AuthContext = Depends(_authorized_context),
    db: Session = Depends(get_db),
) -> AcessoriasSyncResponse:
    if body.company_id is not None:
        company = db.scalar(
            select(ExternalCompany).where(
                ExternalCompany.organization_id == context.organization.id,
                ExternalCompany.id == body.company_id,
            )
        )
        if company is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_id is not valid for this organization.")

    try:
        result = sync_acessorias_period(
            db,
            period=body.period,
            organization=context.organization,
            company_id=body.company_id,
            dry_run=body.dry_run,
            sync_companies=body.sync_companies,
            sync_deliveries=body.sync_deliveries,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AcessoriasConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AcessoriasAuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except AcessoriasRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except (AcessoriasNotFoundError, AcessoriasResponseError, AcessoriasTransportError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    audit_manual_sync(
        db,
        organization_id=context.organization.id,
        actor_id=str(context.user.id),
        period=body.period,
        company_id=body.company_id,
        dry_run=body.dry_run,
        summary=result.summary,
    )
    return AcessoriasSyncResponse(
        run_id=result.run.id if result.run is not None else None,
        status=result.run.status if result.run is not None else "DRY_RUN",
        dry_run=result.dry_run,
        summary=result.summary,
        errors=result.errors,
    )
