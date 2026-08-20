from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache
from backend.app.models.external_company import ExternalCompany
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.integrations.acessorias.client import (
    AcessoriasConfigurationError,
    AcessoriasNotFoundError,
    AcessoriasResponseError,
    AcessoriasTransportError,
    AcessoriasClient,
)
from backend.app.services.integrations.acessorias.sync import sync_acessorias_company
from backend.app.services.integrations.econet.activity_classifier import classify_company_activity_types
from backend.app.services.integrations.econet.enrichment import enrich_cnaes
from backend.app.services.integrations.econet.errors import (
    EconetSessionDisabledError,
    EconetSessionError,
    EconetTransportError,
    EconetUnexpectedResponseError,
)


ACESSORIAS_RETRY_JOB_NAME = "sync_acessorias_company_webhook_retry"
ACESSORIAS_RETRY_DELAY = timedelta(hours=24)
ACESSORIAS_RETRY_MAX_ATTEMPTS = 5


@dataclass(slots=True)
class WebhookCompletionResult:
    company_id: int
    company_active: bool
    acessorias_status: str | None
    acessorias_retry_scheduled: bool
    econet_status: str | None
    econet_missing_cnaes: int
    activity_types: dict[str, int]
    errors: list[dict[str, Any]]


@dataclass(slots=True)
class AcessoriasRetryProcessingResult:
    selected: int
    processed: int
    succeeded: int
    rescheduled: int
    exhausted: int
    cancelled: int
    failed: int
    details: list[dict[str, Any]]


def complete_company_after_econtrole_webhook(
    session: Session,
    *,
    organization: Organization,
    company: ExternalCompany,
) -> WebhookCompletionResult:
    errors: list[dict[str, Any]] = []
    acessorias_status: str | None = None
    acessorias_retry_scheduled = False
    econet_status: str | None = None
    econet_missing_cnaes = 0

    if company.active:
        try:
            acessorias_status, acessorias_retry_scheduled = _sync_company_regime_from_acessorias(
                session,
                organization=organization,
                company=company,
            )
        except Exception as exc:  # defensive: webhook should not fail because of downstream enrich
            errors.append({"scope": "acessorias", "error": str(exc)})

        try:
            econet_status, econet_missing_cnaes = _enrich_missing_company_cnaes_from_econet(
                session,
                organization=organization,
                company=company,
            )
        except Exception as exc:  # defensive: webhook should not fail because of downstream enrich
            errors.append({"scope": "econet", "error": str(exc)})

    try:
        activity_types = classify_company_activity_types(session, company_id=company.id, dry_run=False)
    except Exception as exc:  # defensive: webhook should not fail because of downstream enrich
        activity_types = {"created": 0, "unchanged": 0, "deleted": 0, "desired": 0, "unmapped_cnaes": 0}
        errors.append({"scope": "activity_types", "error": str(exc)})

    return WebhookCompletionResult(
        company_id=company.id,
        company_active=bool(company.active),
        acessorias_status=acessorias_status,
        acessorias_retry_scheduled=acessorias_retry_scheduled,
        econet_status=econet_status,
        econet_missing_cnaes=econet_missing_cnaes,
        activity_types=activity_types,
        errors=errors,
    )


def _sync_company_regime_from_acessorias(
    session: Session,
    *,
    organization: Organization,
    company: ExternalCompany,
) -> tuple[str | None, bool]:
    settings = get_settings()
    if not settings.acessorias_api_token:
        return "SKIPPED_NOT_CONFIGURED", False

    try:
        client = AcessoriasClient.from_settings(settings)
        result = sync_acessorias_company(
            session,
            organization=organization,
            identifier=company.cnpj,
            client=client,
            dry_run=False,
        )
    except AcessoriasConfigurationError:
        return "SKIPPED_NOT_CONFIGURED", False
    except (AcessoriasNotFoundError, AcessoriasTransportError, AcessoriasResponseError):
        _schedule_acessorias_retry(session, organization=organization, company=company)
        return "RETRY_SCHEDULED", True

    if result.payloads_found == 0:
        _schedule_acessorias_retry(session, organization=organization, company=company)
        return "RETRY_SCHEDULED", True

    _close_pending_acessorias_retries(session, organization_id=organization.id, company_id=company.id)
    return "SYNCED", False


def _schedule_acessorias_retry(
    session: Session,
    *,
    organization: Organization,
    company: ExternalCompany,
) -> None:
    existing = _find_pending_acessorias_retry(session, organization_id=organization.id, company_id=company.id)
    now = datetime.now(timezone.utc)
    retry_after = now + ACESSORIAS_RETRY_DELAY
    if existing is not None:
        existing.summary = {
            "reason": "company_not_available_in_acessorias_yet",
            "retry_after": retry_after.isoformat(),
        }
        existing.run_metadata = {
            "company_id": company.id,
            "cnpj": company.cnpj,
            "organization_slug": organization.slug,
            "attempt_count": int((existing.run_metadata or {}).get("attempt_count", 0)),
        }
        return

    session.add(
        IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="ACESSORIAS",
            job_name=ACESSORIAS_RETRY_JOB_NAME,
            status="PENDING",
            started_at=now,
            finished_at=None,
            summary={
                "reason": "company_not_available_in_acessorias_yet",
                "retry_after": retry_after.isoformat(),
            },
            run_metadata={
                "company_id": company.id,
                "cnpj": company.cnpj,
                "organization_slug": organization.slug,
                "attempt_count": 0,
            },
        )
    )


def _close_pending_acessorias_retries(session: Session, *, organization_id: int, company_id: int) -> None:
    now = datetime.now(timezone.utc)
    for run in _list_pending_acessorias_retries(session, organization_id=organization_id, company_id=company_id):
        run.status = "CANCELLED"
        run.finished_at = now


def _find_pending_acessorias_retry(session: Session, *, organization_id: int, company_id: int) -> IntegrationSyncRun | None:
    runs = _list_pending_acessorias_retries(session, organization_id=organization_id, company_id=company_id)
    return runs[0] if runs else None


def _list_pending_acessorias_retries(session: Session, *, organization_id: int, company_id: int) -> list[IntegrationSyncRun]:
    runs = session.scalars(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.organization_id == organization_id,
            IntegrationSyncRun.provider == "ACESSORIAS",
            IntegrationSyncRun.job_name == ACESSORIAS_RETRY_JOB_NAME,
            IntegrationSyncRun.status == "PENDING",
        )
        .order_by(IntegrationSyncRun.id.asc())
    ).all()
    return [run for run in runs if (run.run_metadata or {}).get("company_id") == company_id]


def process_due_acessorias_retries(
    session: Session,
    *,
    limit: int = 100,
    now: datetime | None = None,
) -> AcessoriasRetryProcessingResult:
    observed_now = now or datetime.now(timezone.utc)
    pending_runs = session.scalars(
        select(IntegrationSyncRun)
        .where(
            IntegrationSyncRun.provider == "ACESSORIAS",
            IntegrationSyncRun.job_name == ACESSORIAS_RETRY_JOB_NAME,
            IntegrationSyncRun.status == "PENDING",
        )
        .order_by(IntegrationSyncRun.id.asc())
    ).all()
    due_runs = [run for run in pending_runs if _retry_due_now(run, now=observed_now)][:limit]
    result = AcessoriasRetryProcessingResult(
        selected=len(due_runs),
        processed=0,
        succeeded=0,
        rescheduled=0,
        exhausted=0,
        cancelled=0,
        failed=0,
        details=[],
    )
    for run in due_runs:
        result.processed += 1
        detail = _process_single_acessorias_retry(session, run=run, now=observed_now)
        result.details.append(detail)
        outcome = str(detail.get("outcome"))
        if outcome == "SUCCESS":
            result.succeeded += 1
        elif outcome == "RESCHEDULED":
            result.rescheduled += 1
        elif outcome == "EXHAUSTED":
            result.exhausted += 1
        elif outcome == "CANCELLED":
            result.cancelled += 1
        else:
            result.failed += 1
    session.flush()
    return result


def _retry_due_now(run: IntegrationSyncRun, *, now: datetime) -> bool:
    retry_after = ((run.summary or {}).get("retry_after") if isinstance(run.summary, dict) else None) or None
    if not retry_after:
        return True
    try:
        due_at = datetime.fromisoformat(str(retry_after))
    except ValueError:
        return True
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return due_at <= now


def _process_single_acessorias_retry(
    session: Session,
    *,
    run: IntegrationSyncRun,
    now: datetime,
) -> dict[str, Any]:
    metadata = dict(run.run_metadata or {})
    company_id = metadata.get("company_id")
    organization_slug = metadata.get("organization_slug")
    attempt_count = int(metadata.get("attempt_count", 0))
    if not isinstance(company_id, int):
        run.status = "FAILED"
        run.finished_at = now
        run.error_count = 1
        run.errors = [{"error": "Retry run is missing a valid company_id."}]
        return {"run_id": run.id, "outcome": "FAILED", "reason": "missing_company_id"}

    company = session.get(ExternalCompany, company_id)
    if company is None or not company.active:
        run.status = "CANCELLED"
        run.finished_at = now
        run.summary = {**(run.summary or {}), "reason": "company_missing_or_inactive"}
        return {"run_id": run.id, "company_id": company_id, "outcome": "CANCELLED", "reason": "company_missing_or_inactive"}

    organization = session.get(Organization, company.organization_id)
    if organization is None or organization.slug != organization_slug:
        run.status = "FAILED"
        run.finished_at = now
        run.error_count = 1
        run.errors = [{"error": "Retry run organization mismatch."}]
        return {"run_id": run.id, "company_id": company_id, "outcome": "FAILED", "reason": "organization_mismatch"}

    status, should_retry = _sync_company_regime_from_acessorias(session, organization=organization, company=company)
    if status == "SYNCED":
        run.status = "SUCCESS"
        run.finished_at = now
        run.processed_count = 1
        run.updated_count = 1
        run.summary = {**(run.summary or {}), "result": "synced", "processed_at": now.isoformat()}
        return {"run_id": run.id, "company_id": company_id, "outcome": "SUCCESS", "status": status}

    if not should_retry:
        run.status = "CANCELLED"
        run.finished_at = now
        run.summary = {**(run.summary or {}), "result": status, "processed_at": now.isoformat()}
        return {"run_id": run.id, "company_id": company_id, "outcome": "CANCELLED", "status": status}

    next_attempt = attempt_count + 1
    if next_attempt >= ACESSORIAS_RETRY_MAX_ATTEMPTS:
        run.status = "EXHAUSTED"
        run.finished_at = now
        run.error_count = 1
        run.summary = {
            **(run.summary or {}),
            "result": status,
            "attempt_count": next_attempt,
            "processed_at": now.isoformat(),
            "reason": "max_attempts_reached",
        }
        return {"run_id": run.id, "company_id": company_id, "outcome": "EXHAUSTED", "status": status, "attempt_count": next_attempt}

    retry_after = now + ACESSORIAS_RETRY_DELAY
    run.status = "PENDING"
    run.started_at = now
    run.finished_at = None
    run.summary = {
        **(run.summary or {}),
        "result": status,
        "retry_after": retry_after.isoformat(),
        "last_attempt_at": now.isoformat(),
    }
    run.run_metadata = {
        **metadata,
        "company_id": company.id,
        "cnpj": company.cnpj,
        "organization_slug": organization.slug,
        "attempt_count": next_attempt,
    }
    return {
        "run_id": run.id,
        "company_id": company_id,
        "outcome": "RESCHEDULED",
        "status": status,
        "attempt_count": next_attempt,
        "retry_after": retry_after.isoformat(),
    }


def _enrich_missing_company_cnaes_from_econet(
    session: Session,
    *,
    organization: Organization,
    company: ExternalCompany,
) -> tuple[str | None, int]:
    settings = get_settings()
    if not settings.econet_assisted_session_enabled:
        return "SKIPPED_NOT_CONFIGURED", 0

    missing_cnaes = session.scalars(
        select(CompanyCnae.cnae)
        .outerjoin(EconetCnaeCache, EconetCnaeCache.cnae == CompanyCnae.cnae)
        .where(
            CompanyCnae.company_id == company.id,
            CompanyCnae.active.is_(True),
            EconetCnaeCache.id.is_(None),
        )
        .distinct()
        .order_by(CompanyCnae.cnae.asc())
    ).all()
    if not missing_cnaes:
        return "SKIPPED_CACHE_COMPLETE", 0

    try:
        result = enrich_cnaes(
            session,
            organization_id=organization.id,
            cnaes=missing_cnaes,
            company_ids=[company.id],
            limit=len(missing_cnaes),
            dry_run=False,
            cache_only=False,
            force_refresh=False,
            sync_catalog=False,
            classify_companies=False,
            settings=settings,
        )
    except (EconetSessionDisabledError, EconetSessionError, EconetTransportError, EconetUnexpectedResponseError) as exc:
        return f"FAILED_{exc.__class__.__name__}", len(missing_cnaes)
    return result.status, len(missing_cnaes)
