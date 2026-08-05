from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_auth_context, require_roles
from backend.app.core.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.schemas.econet import (
    EconetEnrichmentRequest,
    EconetEnrichmentResponse,
    EconetSessionClearResponse,
    EconetSessionImportRequest,
    EconetEnrichmentItemResponse,
    FactorRPotentialResponse,
    EconetSessionProbeResponse,
    EconetSessionStatusResponse,
)
from backend.app.services.auth import AuthContext, ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.app.services.integrations.econtrole.sync import resolve_target_organization
from backend.app.services.integrations.econet.assisted_session import get_econet_assisted_session
from backend.app.services.integrations.econet.client import EconetClient
from backend.app.services.integrations.econet.enrichment import enrich_cnaes
from backend.app.services.integrations.econet.errors import (
    EconetSessionDisabledError,
    EconetSessionExpiredError,
    EconetSessionInvalidError,
    EconetSessionNotLoadedError,
    EconetTransportError,
    EconetUnexpectedContentTypeError,
    EconetUnexpectedRedirectError,
    EconetUnexpectedResponseError,
)

router = APIRouter(prefix="/integrations/econet", tags=["integrations"])


def _admin_context(
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


def _read_context(
    _: object = Depends(require_roles(ROLE_VIEW, ROLE_ADMIN, ROLE_DEV)),
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthContext:
    return context


@router.post("/session/import", response_model=EconetSessionStatusResponse)
def import_econet_session(
    body: EconetSessionImportRequest,
    _: AuthContext = Depends(_admin_context),
) -> EconetSessionStatusResponse:
    settings = get_settings()
    session = get_econet_assisted_session(settings)
    try:
        snapshot = session.import_storage_state(body.model_dump())
    except EconetSessionDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except EconetSessionInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EconetSessionStatusResponse(**snapshot, message="Sessao Econet carregada; probe ainda nao executado.")


@router.get("/session/status", response_model=EconetSessionStatusResponse)
def get_econet_session_status(
    _: AuthContext = Depends(_read_context),
) -> EconetSessionStatusResponse:
    snapshot = get_econet_assisted_session(get_settings()).snapshot()
    return EconetSessionStatusResponse(**snapshot)


@router.post("/session/probe", response_model=EconetSessionProbeResponse)
def probe_econet_session(
    _: AuthContext = Depends(_admin_context),
) -> EconetSessionProbeResponse:
    settings = get_settings()
    try:
        with EconetClient(settings=settings) as client:
            snapshot = client.probe_session()
    except EconetSessionDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except EconetSessionNotLoadedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (EconetSessionExpiredError, EconetUnexpectedRedirectError) as exc:
        snapshot = get_econet_assisted_session(settings).snapshot()
        return EconetSessionProbeResponse(**snapshot, message=str(exc))
    except (EconetTransportError, EconetUnexpectedContentTypeError, EconetUnexpectedResponseError) as exc:
        snapshot = get_econet_assisted_session(settings).snapshot()
        return EconetSessionProbeResponse(**snapshot, message=str(exc))
    return EconetSessionProbeResponse(**snapshot, message="Sessao Econet validada.")


@router.delete("/session", response_model=EconetSessionClearResponse)
def clear_econet_session(
    _: AuthContext = Depends(_admin_context),
) -> EconetSessionClearResponse:
    snapshot = get_econet_assisted_session(get_settings()).clear()
    return EconetSessionClearResponse(**snapshot, message="Sessao Econet removida da memoria.")


@router.post("/enrich", response_model=EconetEnrichmentResponse)
def enrich_econet_cnaes(
    body: EconetEnrichmentRequest,
    context: AuthContext = Depends(_admin_context),
    db: Session = Depends(get_db),
) -> EconetEnrichmentResponse:
    organization = context.organization
    if body.organization_slug:
        organization = resolve_target_organization(db, body.organization_slug)
    sync_run = IntegrationSyncRun(
        organization_id=organization.id,
        provider="ECONET",
        job_name="enrich_cnaes_econet",
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        summary={"dry_run": body.dry_run},
        run_metadata={"company_ids": body.company_ids or [], "cnaes": body.cnaes or []},
    )
    db.add(sync_run)
    db.flush()
    result = enrich_cnaes(
        db,
        organization_id=organization.id,
        cnaes=body.cnaes,
        company_ids=body.company_ids,
        limit=body.limit,
        dry_run=body.dry_run,
        cache_only=body.cache_only,
        force_refresh=body.force_refresh,
        sync_catalog=body.sync_catalog,
        classify_companies=body.classify_companies,
    )
    sync_run.status = result.status
    sync_run.finished_at = datetime.now(timezone.utc)
    sync_run.processed_count = int(result.summary.get("processed", 0))
    sync_run.created_count = int(result.summary.get("created", 0))
    sync_run.updated_count = int(result.summary.get("updated", 0))
    sync_run.error_count = int(result.summary.get("errors", 0))
    sync_run.summary = result.summary
    if body.dry_run:
        db.rollback()
    else:
        db.commit()
    factor_r_results = getattr(result, "factor_r_results", None)
    return EconetEnrichmentResponse(
        run_id=sync_run.id if not body.dry_run else None,
        status=result.status,
        dry_run=result.dry_run,
        summary=result.summary,
        items=[EconetEnrichmentItemResponse(**asdict(item)) for item in result.items],
        catalog_summary=result.catalog_summary,
        factor_r_results=(
            [
                FactorRPotentialResponse(
                    company_id=item.company_id,
                    status=item.status,
                    factor_r_potential=item.factor_r_potential,
                    cnaes_total=item.cnaes_total,
                    cnaes_with_cache=item.cnaes_with_cache,
                    positive_cnaes=item.positive_cnaes,
                    negative_cnaes=item.negative_cnaes,
                    missing_cnaes=item.missing_cnaes,
                    annex_default=item.annex_default,
                    annex_conditional=item.annex_conditional,
                    factor_r_threshold=item.factor_r_threshold,
                )
                for item in factor_r_results
            ]
            if factor_r_results is not None
            else None
        ),
    )
