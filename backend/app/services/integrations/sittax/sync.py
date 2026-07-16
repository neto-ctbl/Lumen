from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import mask_value
from backend.app.models.external_company import ExternalCompany
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.services.integrations.econtrole.sync import resolve_target_organization

from .client import FixtureSittaxClient, SittaxClient
from .errors import SittaxResponseError
from .mapper import map_company_item
from .session import SittaxSession


FIXTURE_DIR = Path("backend/tests/fixtures/sittax")
DEFAULT_LOGIN_FIXTURE = FIXTURE_DIR / "login_success.json"
DEFAULT_COMPANIES_FIXTURE = FIXTURE_DIR / "companies_success.json"

MATCHED = "MATCHED"
UNMATCHED = "UNMATCHED"
AMBIGUOUS = "AMBIGUOUS"
INVALID_CNPJ = "INVALID_CNPJ"


@dataclass(slots=True)
class SittaxCompanyMatchResult:
    company_id: int | None
    match_status: str


@dataclass(slots=True)
class SittaxCompanySyncSummary:
    companies_received: int = 0
    companies_valid: int = 0
    companies_invalid: int = 0
    companies_matched: int = 0
    companies_unmatched: int = 0
    companies_ambiguous: int = 0
    snapshots_created: int = 0
    snapshots_updated: int = 0
    snapshots_unchanged: int = 0
    failures: int = 0
    snapshots_missing_from_source: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "companies_received": self.companies_received,
            "companies_valid": self.companies_valid,
            "companies_invalid": self.companies_invalid,
            "companies_matched": self.companies_matched,
            "companies_unmatched": self.companies_unmatched,
            "companies_ambiguous": self.companies_ambiguous,
            "snapshots_created": self.snapshots_created,
            "snapshots_updated": self.snapshots_updated,
            "snapshots_unchanged": self.snapshots_unchanged,
            "failures": self.failures,
            "snapshots_missing_from_source": self.snapshots_missing_from_source,
        }


@dataclass(slots=True)
class SittaxCompanySyncResult:
    run: IntegrationSyncRun | None
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    dry_run: bool
    fixture_mode: bool
    status: str


def build_fixture_sittax_client(*, companies_fixture: str | Path | None = None) -> FixtureSittaxClient:
    settings = get_settings()
    session = SittaxSession.from_settings(settings)
    return FixtureSittaxClient.from_files(
        session=session,
        login_path=DEFAULT_LOGIN_FIXTURE,
        companies_path=companies_fixture or DEFAULT_COMPANIES_FIXTURE,
    )


def reconcile_external_company_candidates(candidates: list[ExternalCompany]) -> SittaxCompanyMatchResult:
    active_candidates = [candidate for candidate in candidates if candidate.active]
    if len(active_candidates) == 1:
        return SittaxCompanyMatchResult(company_id=active_candidates[0].id, match_status=MATCHED)
    if len(active_candidates) > 1:
        return SittaxCompanyMatchResult(company_id=None, match_status=AMBIGUOUS)
    return SittaxCompanyMatchResult(company_id=None, match_status=UNMATCHED)


def sync_sittax_companies(
    session: Session,
    *,
    org_slug: str | None = None,
    organization: Organization | None = None,
    dry_run: bool = False,
    companies_fixture: str | Path | None = None,
    client: SittaxClient | FixtureSittaxClient | None = None,
) -> SittaxCompanySyncResult:
    if organization is None:
        organization = resolve_target_organization(session, org_slug)

    settings = get_settings()
    fixture_mode = companies_fixture is not None
    created_client = False
    if client is None:
        created_client = True
        client = (
            build_fixture_sittax_client(companies_fixture=companies_fixture)
            if fixture_mode
            else SittaxClient(session=SittaxSession.from_settings(settings))
        )

    summary = SittaxCompanySyncSummary()
    errors: list[dict[str, Any]] = []
    run: IntegrationSyncRun | None = None
    status = "DRY_RUN" if dry_run else "RUNNING"

    if not dry_run:
        run = IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="SITTAX",
            job_name="sync_sittax_companies",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            summary={},
            run_metadata={
                "organization_slug": organization.slug,
                "fixture_mode": fixture_mode,
                "dry_run": False,
            },
        )
        session.add(run)
        session.commit()

    try:
        with client.session.exclusive():
            client.authenticate_with_settings(settings)
            company_payloads = client.list_companies_payloads()

        observed_at = datetime.now(timezone.utc)
        summary.companies_received = len(company_payloads)
        seen_company_ids: set[str] = set()

        for payload in company_payloads:
            sittax_company_id = str(payload.get("id", "unknown")).strip() or "unknown"
            try:
                mapped = map_company_item(payload)
            except SittaxResponseError as exc:
                summary.companies_invalid += 1
                summary.failures += 1
                errors.append(
                    {
                        "scope": "company",
                        "sittax_company_id": mask_value(sittax_company_id, visible_prefix=2, visible_suffix=2),
                        "match_status": INVALID_CNPJ,
                        "error": str(exc),
                    }
                )
                continue

            summary.companies_valid += 1
            seen_company_ids.add(mapped.external_id)
            match = _reconcile_external_company(session, organization_id=organization.id, cnpj=mapped.cnpj)
            if match.match_status == MATCHED:
                summary.companies_matched += 1
            elif match.match_status == AMBIGUOUS:
                summary.companies_ambiguous += 1
            else:
                summary.companies_unmatched += 1

            if dry_run:
                continue

            snapshot = session.scalar(
                select(SittaxCompanySnapshot).where(
                    SittaxCompanySnapshot.organization_id == organization.id,
                    SittaxCompanySnapshot.sittax_company_id == mapped.external_id,
                )
            )
            if snapshot is None:
                snapshot = SittaxCompanySnapshot(
                    organization_id=organization.id,
                    company_id=match.company_id,
                    sittax_company_id=mapped.external_id,
                    cnpj=mapped.cnpj,
                    legal_name=mapped.legal_name,
                    trade_name=mapped.trade_name,
                    state_registration=mapped.state_registration,
                    state=mapped.state,
                    status=mapped.status,
                    homologated=mapped.homologated,
                    cash_regime=mapped.cash_regime,
                    match_status=match.match_status,
                    raw_payload=mapped.raw_payload,
                    first_seen_at=observed_at,
                    last_seen_at=observed_at,
                )
                session.add(snapshot)
                session.flush()
                summary.snapshots_created += 1
                continue

            changed = _apply_snapshot_update(snapshot=snapshot, mapped=mapped, match=match, observed_at=observed_at)
            session.flush()
            if changed:
                summary.snapshots_updated += 1
            else:
                summary.snapshots_unchanged += 1

        if dry_run:
            existing_count = session.scalar(
                select(func.count()).select_from(SittaxCompanySnapshot).where(
                    SittaxCompanySnapshot.organization_id == organization.id
                )
            )
            summary.snapshots_missing_from_source = max(int(existing_count or 0) - len(seen_company_ids), 0)
        else:
            summary.snapshots_missing_from_source = _count_missing_snapshots(
                session,
                organization_id=organization.id,
                seen_company_ids=seen_company_ids,
            )
            status = _resolve_run_status(summary=summary)
            assert run is not None
            run.finished_at = datetime.now(timezone.utc)
            run.processed_count = summary.companies_received
            run.created_count = summary.snapshots_created
            run.updated_count = summary.snapshots_updated
            run.error_count = summary.failures
            run.errors = errors or None
            run.summary = summary.to_dict()
            run.status = status
            session.commit()

        return SittaxCompanySyncResult(
            run=run,
            summary=summary.to_dict(),
            errors=errors,
            dry_run=dry_run,
            fixture_mode=fixture_mode,
            status=status,
        )
    except Exception as exc:
        if not dry_run and run is not None:
            session.rollback()
            failed_run = session.get(IntegrationSyncRun, run.id)
            if failed_run is not None:
                failed_run.finished_at = datetime.now(timezone.utc)
                failed_run.status = "FAILED"
                failed_run.error_count = max(summary.failures, 1)
                failed_run.errors = (errors or []) + [{"scope": "global", "error": exc.__class__.__name__}]
                failed_run.summary = summary.to_dict()
                failed_run.run_metadata = {
                    "organization_slug": organization.slug,
                    "fixture_mode": fixture_mode,
                    "dry_run": False,
                }
                session.commit()
        raise
    finally:
        if created_client:
            client.close()


def _reconcile_external_company(session: Session, *, organization_id: int, cnpj: str) -> SittaxCompanyMatchResult:
    candidates = session.scalars(
        select(ExternalCompany).where(
            ExternalCompany.organization_id == organization_id,
            ExternalCompany.cnpj == cnpj,
        )
    ).all()
    return reconcile_external_company_candidates(candidates)


def _apply_snapshot_update(
    *,
    snapshot: SittaxCompanySnapshot,
    mapped,
    match: SittaxCompanyMatchResult,
    observed_at: datetime,
) -> bool:
    changed = False
    updates = {
        "company_id": match.company_id,
        "cnpj": mapped.cnpj,
        "legal_name": mapped.legal_name,
        "trade_name": mapped.trade_name,
        "state_registration": mapped.state_registration,
        "state": mapped.state,
        "status": mapped.status,
        "homologated": mapped.homologated,
        "cash_regime": mapped.cash_regime,
        "match_status": match.match_status,
        "raw_payload": mapped.raw_payload,
    }
    for field, value in updates.items():
        if getattr(snapshot, field) != value:
            setattr(snapshot, field, value)
            changed = True
    snapshot.last_seen_at = observed_at
    return changed


def _count_missing_snapshots(session: Session, *, organization_id: int, seen_company_ids: set[str]) -> int:
    rows = session.scalars(
        select(SittaxCompanySnapshot.sittax_company_id).where(SittaxCompanySnapshot.organization_id == organization_id)
    ).all()
    return sum(1 for company_id in rows if company_id not in seen_company_ids)


def _resolve_run_status(*, summary: SittaxCompanySyncSummary) -> str:
    if summary.failures > 0:
        return "PARTIAL"
    return "SUCCESS"
