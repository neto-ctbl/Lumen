from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.core.config import get_settings
from backend.app.services.audit import record_audit_event
from backend.app.services.integrations.econtrole.mapper import EControleMappingError
from backend.app.services.integrations.econtrole.sync import (
    delete_company_from_econtrole_payload,
    resolve_target_organization,
    upsert_company_from_econtrole_payload,
)


router = APIRouter(prefix="/webhooks/econtrole", tags=["webhooks"])


def require_econtrole_webhook_token(
    x_lumen_webhook_token: str | None = Header(default=None, alias="X-Lumen-Webhook-Token"),
) -> None:
    configured_token = get_settings().econtrole_webhook_token
    if not configured_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook token is not configured.")
    if not x_lumen_webhook_token or x_lumen_webhook_token != configured_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token.")


@router.post("/company-upsert")
def company_upsert(
    payload: dict[str, Any],
    _: None = Depends(require_econtrole_webhook_token),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        organization = resolve_target_organization(db, payload.get("org_slug"))
        result = upsert_company_from_econtrole_payload(db, organization=organization, payload=payload)
    except EControleMappingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_audit_event(
        db,
        event_type="webhook.econtrole.company_upsert",
        message=f"eControle company upsert processed for org {organization.slug}.",
        actor_type="system",
        actor_id="econtrole-webhook",
        resource_type="external_company",
        resource_id=str(result.company.id),
        event_metadata={"organization_id": organization.id, "created": result.created, "updated": result.updated},
        raw_payload=payload,
    )
    db.commit()
    return {
        "status": "ok",
        "company_id": result.company.id,
        "created": result.created,
        "updated": result.updated,
    }


@router.post("/company-delete")
def company_delete(
    payload: dict[str, Any],
    _: None = Depends(require_econtrole_webhook_token),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        organization = resolve_target_organization(db, payload.get("org_slug"))
        result = delete_company_from_econtrole_payload(db, organization=organization, payload=payload)
    except EControleMappingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    record_audit_event(
        db,
        event_type="webhook.econtrole.company_delete",
        message=f"eControle company delete processed for org {organization.slug}.",
        actor_type="system",
        actor_id="econtrole-webhook",
        resource_type="external_company",
        resource_id=str(result.company.id),
        event_metadata={"organization_id": organization.id, "deleted": result.deleted},
        raw_payload=payload,
    )
    db.commit()
    return {
        "status": "ok",
        "company_id": result.company.id,
        "deleted": result.deleted,
    }
