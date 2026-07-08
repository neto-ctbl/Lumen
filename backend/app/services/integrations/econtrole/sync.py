from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.econtrole.mapper import EControleMappingError, map_econtrole_company_payload, normalize_cnpj


SYNC_STATUS_SYNCED = "SYNCED"
SYNC_STATUS_DELETED = "DELETED_ECONTROLE"


@dataclass(slots=True)
class CompanyUpsertResult:
    company: ExternalCompany
    created: bool
    updated: bool


@dataclass(slots=True)
class CompanyDeleteResult:
    company: ExternalCompany
    deleted: bool


@dataclass(slots=True)
class SyncBatchResult:
    processed_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    error_count: int = 0
    errors: list[dict[str, Any]] | None = None


def resolve_target_organization(session: Session, org_slug: str | None = None) -> Organization:
    if org_slug:
        organization = session.execute(select(Organization).where(Organization.slug == org_slug)).scalar_one_or_none()
        if organization is None:
            raise ValueError(f"Organization with slug '{org_slug}' was not found.")
        if not organization.is_active:
            raise ValueError(f"Organization with slug '{org_slug}' is inactive.")
        return organization

    settings = get_settings()
    if settings.app_env not in {"local", "development", "dev", "test"}:
        raise ValueError("org_slug is required outside local/MVP environments.")

    organizations = list(
        session.execute(
            select(Organization).where(Organization.is_active.is_(True)).order_by(Organization.id.asc())
        ).scalars()
    )
    if not organizations:
        raise ValueError("No active organization found. Create one first or pass org_slug.")
    if len(organizations) > 1:
        raise ValueError("Multiple active organizations found. Provide org_slug explicitly.")
    return organizations[0]


def upsert_company_from_econtrole_payload(
    session: Session,
    *,
    organization: Organization,
    payload: dict[str, Any],
) -> CompanyUpsertResult:
    mapped = map_econtrole_company_payload(payload)
    company = session.execute(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization.id,
            ExternalCompany.cnpj == mapped["cnpj"],
        )
    ).scalar_one_or_none()

    created = company is None
    if company is None:
        company = ExternalCompany(organization_id=organization.id, cnpj=mapped["cnpj"], razao_social=mapped["razao_social"])
        session.add(company)

    updated = _apply_upsert(company, mapped)
    session.flush()
    return CompanyUpsertResult(company=company, created=created, updated=updated or created)


def delete_company_from_econtrole_payload(
    session: Session,
    *,
    organization: Organization,
    payload: dict[str, Any],
) -> CompanyDeleteResult:
    normalized_cnpj = normalize_cnpj(payload.get("cnpj"))
    econtrole_company_id = payload.get("id")
    deleted_at = _resolve_deleted_at(payload)

    company = None
    if normalized_cnpj:
        company = session.execute(
            select(ExternalCompany).where(
                ExternalCompany.organization_id == organization.id,
                ExternalCompany.cnpj == normalized_cnpj,
            )
        ).scalar_one_or_none()
    if company is None and econtrole_company_id is not None:
        company = session.execute(
            select(ExternalCompany).where(
                ExternalCompany.organization_id == organization.id,
                ExternalCompany.econtrole_company_id == str(econtrole_company_id),
            )
        ).scalar_one_or_none()

    if company is None:
        raise EControleMappingError("Delete payload must match an existing company by cnpj or id.")

    already_deleted = company.active is False and company.sync_status == SYNC_STATUS_DELETED
    company.active = False
    company.sync_status = SYNC_STATUS_DELETED
    company.deleted_at_econtrole = deleted_at
    if payload:
        company.raw_econtrole = payload
    session.flush()
    return CompanyDeleteResult(company=company, deleted=not already_deleted)


def sync_companies_batch(
    session: Session,
    *,
    organization: Organization,
    payloads: list[dict[str, Any]],
) -> SyncBatchResult:
    result = SyncBatchResult(processed_count=len(payloads), errors=[])
    for payload in payloads:
        try:
            upsert_result = upsert_company_from_econtrole_payload(session, organization=organization, payload=payload)
        except Exception as exc:
            result.error_count += 1
            result.errors.append(
                {
                    "company_id": payload.get("id"),
                    "cnpj": payload.get("cnpj"),
                    "error": str(exc),
                }
            )
            continue

        if upsert_result.created:
            result.created_count += 1
        elif upsert_result.updated:
            result.updated_count += 1

    if not result.errors:
        result.errors = None
    return result


def _apply_upsert(company: ExternalCompany, mapped: dict[str, Any]) -> bool:
    changed = False
    for field, value in mapped.items():
        if getattr(company, field) != value:
            setattr(company, field, value)
            changed = True

    if company.active is not True:
        company.active = True
        changed = True
    if company.deleted_at_econtrole is not None:
        company.deleted_at_econtrole = None
        changed = True
    if company.sync_status != SYNC_STATUS_SYNCED:
        company.sync_status = SYNC_STATUS_SYNCED
        changed = True
    return changed


def _resolve_deleted_at(payload: dict[str, Any]) -> datetime:
    for field in ("deleted_at", "deletedAt", "updated_at", "updatedAt"):
        value = payload.get(field)
        if value:
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))
    return datetime.now(timezone.utc)
