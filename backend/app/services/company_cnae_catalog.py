from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.external_company import ExternalCompany
from backend.app.services.integrations.econet.parser import format_cnae, normalize_cnae


CATALOG_SOURCE_ECONTROLE = "ECONTROLE"
INVALID_PLACEHOLDER_CNAES = {"0000000"}


@dataclass(frozen=True, slots=True)
class NormalizedCompanyCnae:
    cnae: str
    cnae_formatted: str
    is_primary: bool


@dataclass(frozen=True, slots=True)
class CompanyCnaeMutation:
    cnae: str
    operation: str
    is_primary: bool


@dataclass(slots=True)
class CompanyCnaeSyncResult:
    company_id: int
    source: str
    company_active: bool
    dry_run: bool
    cnaes_received: int = 0
    cnaes_valid: int = 0
    cnaes_invalid: int = 0
    created: int = 0
    updated: int = 0
    reactivated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    invalid_cnaes: list[str] = field(default_factory=list)
    mutations: list[CompanyCnaeMutation] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int | bool]:
        return {
            "company_id": self.company_id,
            "dry_run": self.dry_run,
            "company_active": self.company_active,
            "cnaes_received": self.cnaes_received,
            "cnaes_valid": self.cnaes_valid,
            "cnaes_invalid": self.cnaes_invalid,
            "cnaes_created": self.created,
            "cnaes_updated": self.updated,
            "cnaes_reactivated": self.reactivated,
            "cnaes_deactivated": self.deactivated,
            "cnaes_unchanged": self.unchanged,
        }


def normalize_company_cnaes(
    *,
    primary_cnae: str | None,
    secondary_cnaes: Iterable[object] | None,
) -> tuple[list[NormalizedCompanyCnae], list[str], int]:
    desired: dict[str, NormalizedCompanyCnae] = {}
    invalid: list[str] = []
    received = 0

    def ingest(raw_value: object, *, is_primary: bool) -> None:
        nonlocal received
        if raw_value is None:
            return
        text = str(raw_value).strip()
        if not text:
            return
        received += 1
        try:
            cnae = normalize_cnae(text)
        except Exception:
            invalid.append(text)
            return
        if cnae in INVALID_PLACEHOLDER_CNAES:
            invalid.append(text)
            return
        normalized = NormalizedCompanyCnae(cnae=cnae, cnae_formatted=format_cnae(cnae), is_primary=is_primary)
        current = desired.get(cnae)
        if current is None or (is_primary and not current.is_primary):
            desired[cnae] = normalized

    ingest(primary_cnae, is_primary=True)
    for value in secondary_cnaes or ():
        ingest(value, is_primary=False)
    ordered = sorted(desired.values(), key=lambda item: (not item.is_primary, item.cnae))
    return ordered, invalid, received


def sync_company_cnae_catalog(
    session: Session,
    *,
    company: ExternalCompany,
    primary_cnae: str | None = None,
    secondary_cnaes: Iterable[object] | None = None,
    source: str = CATALOG_SOURCE_ECONTROLE,
    dry_run: bool = False,
    observed_at: datetime | None = None,
) -> CompanyCnaeSyncResult:
    observed = observed_at or datetime.now(timezone.utc)
    normalized_items, invalid_items, received = normalize_company_cnaes(
        primary_cnae=company.cnae_principal if primary_cnae is None else primary_cnae,
        secondary_cnaes=company.cnaes_secundarios if secondary_cnaes is None else secondary_cnaes,
    )
    result = CompanyCnaeSyncResult(
        company_id=company.id,
        source=source,
        company_active=bool(company.active),
        dry_run=dry_run,
        cnaes_received=received,
        cnaes_valid=len(normalized_items),
        cnaes_invalid=len(invalid_items),
        invalid_cnaes=invalid_items,
    )

    existing_rows = session.scalars(
        select(CompanyCnae).where(CompanyCnae.company_id == company.id).order_by(CompanyCnae.id.asc())
    ).all()
    existing_by_cnae = {row.cnae: row for row in existing_rows}
    desired_by_cnae = {item.cnae: item for item in normalized_items}

    if company.active:
        for item in normalized_items:
            current = existing_by_cnae.get(item.cnae)
            if current is None:
                _record_create(session, result, item=item, company=company, source=source, observed_at=observed, dry_run=dry_run)
                continue
            if not current.active:
                _record_reactivate(current, result, item=item, observed_at=observed, dry_run=dry_run)
                continue
            changed = False
            if current.is_primary != item.is_primary:
                changed = True
                if not dry_run:
                    current.is_primary = item.is_primary
            if current.cnae_formatted != item.cnae_formatted:
                changed = True
                if not dry_run:
                    current.cnae_formatted = item.cnae_formatted
            if current.source != source:
                changed = True
                if not dry_run:
                    current.source = source
            if not dry_run:
                current.last_seen_at = observed
                current.deactivated_at = None
            if changed:
                result.updated += 1
                result.mutations.append(CompanyCnaeMutation(cnae=item.cnae, operation="WOULD_UPDATE" if dry_run else "UPDATED", is_primary=item.is_primary))
            else:
                result.unchanged += 1
                result.mutations.append(
                    CompanyCnaeMutation(
                        cnae=item.cnae,
                        operation="WOULD_REMAIN_UNCHANGED" if dry_run else "UNCHANGED",
                        is_primary=item.is_primary,
                    )
                )
    for row in existing_rows:
        if not row.active:
            continue
        if not company.active or row.cnae not in desired_by_cnae:
            if dry_run:
                result.deactivated += 1
                result.mutations.append(CompanyCnaeMutation(cnae=row.cnae, operation="WOULD_DEACTIVATE", is_primary=row.is_primary))
                continue
            row.active = False
            row.is_primary = False
            row.deactivated_at = observed
            row.last_seen_at = observed
            result.deactivated += 1
            result.mutations.append(CompanyCnaeMutation(cnae=row.cnae, operation="DEACTIVATED", is_primary=False))

    if not dry_run:
        session.flush()
    return result


def sync_organization_cnae_catalog(
    session: Session,
    *,
    organization_id: int,
    company_id: int | None = None,
    only_active: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
    observed_at: datetime | None = None,
) -> list[CompanyCnaeSyncResult]:
    query: Select[tuple[ExternalCompany]] = select(ExternalCompany).where(ExternalCompany.organization_id == organization_id)
    if company_id is not None:
        query = query.where(ExternalCompany.id == company_id)
    if only_active:
        query = query.where(ExternalCompany.active.is_(True))
    query = query.order_by(ExternalCompany.id.asc())
    if limit is not None:
        query = query.limit(limit)
    companies = session.scalars(query).all()
    return [
        sync_company_cnae_catalog(session, company=company, dry_run=dry_run, observed_at=observed_at)
        for company in companies
    ]


def get_active_company_cnaes(session: Session, *, company_id: int) -> list[CompanyCnae]:
    return session.scalars(
        select(CompanyCnae)
        .where(CompanyCnae.company_id == company_id, CompanyCnae.active.is_(True))
        .order_by(CompanyCnae.is_primary.desc(), CompanyCnae.cnae.asc())
    ).all()


def get_unique_active_cnaes(
    session: Session,
    *,
    organization_id: int | None = None,
    company_ids: Iterable[int] | None = None,
) -> list[str]:
    query = (
        select(CompanyCnae.cnae)
        .join(ExternalCompany, ExternalCompany.id == CompanyCnae.company_id)
        .where(CompanyCnae.active.is_(True))
        .distinct()
        .order_by(CompanyCnae.cnae.asc())
    )
    if organization_id is not None:
        query = query.where(ExternalCompany.organization_id == organization_id)
    if company_ids is not None:
        company_ids = list(company_ids)
        if company_ids:
            query = query.where(CompanyCnae.company_id.in_(company_ids))
        else:
            return []
    return list(session.scalars(query).all())


def _record_create(
    session: Session,
    result: CompanyCnaeSyncResult,
    *,
    item: NormalizedCompanyCnae,
    company: ExternalCompany,
    source: str,
    observed_at: datetime,
    dry_run: bool,
) -> None:
    if dry_run:
        result.created += 1
        result.mutations.append(CompanyCnaeMutation(cnae=item.cnae, operation="WOULD_CREATE", is_primary=item.is_primary))
        return
    session.add(
        CompanyCnae(
            company_id=company.id,
            cnae=item.cnae,
            cnae_formatted=item.cnae_formatted,
            is_primary=item.is_primary,
            source=source,
            active=True,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
            deactivated_at=None,
        )
    )
    result.created += 1
    result.mutations.append(CompanyCnaeMutation(cnae=item.cnae, operation="CREATED", is_primary=item.is_primary))


def _record_reactivate(
    row: CompanyCnae,
    result: CompanyCnaeSyncResult,
    *,
    item: NormalizedCompanyCnae,
    observed_at: datetime,
    dry_run: bool,
) -> None:
    if dry_run:
        result.reactivated += 1
        result.mutations.append(CompanyCnaeMutation(cnae=item.cnae, operation="WOULD_REACTIVATE", is_primary=item.is_primary))
        return
    row.active = True
    row.is_primary = item.is_primary
    row.cnae_formatted = item.cnae_formatted
    row.last_seen_at = observed_at
    row.deactivated_at = None
    result.reactivated += 1
    result.mutations.append(CompanyCnaeMutation(cnae=item.cnae, operation="REACTIVATED", is_primary=item.is_primary))
