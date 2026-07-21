from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.security import mask_value
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.models.sittax_company_snapshot import SittaxCompanySnapshot
from backend.app.models.sittax_difal_snapshot import SittaxDifalSnapshot
from backend.app.models.sittax_fiscal_document_snapshot import SittaxFiscalDocumentSnapshot
from backend.app.models.sittax_task_snapshot import SittaxTaskSnapshot
from backend.app.services.integrations.econtrole.sync import resolve_target_organization

from .client import FixtureSittaxClient, SittaxClient
from .errors import SittaxContextMismatchError, SittaxPaginationError, SittaxResponseError
from .mapper import map_company_item
from .session import SittaxSession


FIXTURE_DIR = Path("backend/tests/fixtures/sittax")
DEFAULT_LOGIN_FIXTURE = FIXTURE_DIR / "login_success.json"
DEFAULT_COMPANIES_FIXTURE = FIXTURE_DIR / "companies_success.json"
DEFAULT_APURACAO_FIXTURE = FIXTURE_DIR / "apuracao_success.json"
DEFAULT_DIFAL_FIXTURE = FIXTURE_DIR / "difal_with_guide.json"
DEFAULT_ENTRY_DOCUMENTS_FIXTURE = FIXTURE_DIR / "fiscal_documents_entry_page.json"
DEFAULT_EXIT_DOCUMENTS_FIXTURE = FIXTURE_DIR / "fiscal_documents_exit_page.json"
DEFAULT_TASKS_FIXTURE = FIXTURE_DIR / "tasks_page.json"
INTERFACE_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")

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


@dataclass(slots=True)
class SittaxApuracaoSyncSummary:
    companies_selected: int = 0
    companies_processed: int = 0
    companies_skipped_unmatched: int = 0
    companies_skipped_ambiguous: int = 0
    companies_skipped_invalid: int = 0
    apuracoes_received: int = 0
    snapshots_created: int = 0
    snapshots_updated: int = 0
    snapshots_unchanged: int = 0
    context_mismatches: int = 0
    not_found: int = 0
    failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "companies_selected": self.companies_selected,
            "companies_processed": self.companies_processed,
            "companies_skipped_unmatched": self.companies_skipped_unmatched,
            "companies_skipped_ambiguous": self.companies_skipped_ambiguous,
            "companies_skipped_invalid": self.companies_skipped_invalid,
            "apuracoes_received": self.apuracoes_received,
            "snapshots_created": self.snapshots_created,
            "snapshots_updated": self.snapshots_updated,
            "snapshots_unchanged": self.snapshots_unchanged,
            "context_mismatches": self.context_mismatches,
            "not_found": self.not_found,
            "failures": self.failures,
        }


@dataclass(slots=True)
class SittaxApuracaoSyncResult:
    run: IntegrationSyncRun | None
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    dry_run: bool
    fixture_mode: bool
    status: str


@dataclass(slots=True)
class SittaxOperationalSyncSummary:
    companies_selected: int = 0
    companies_processed: int = 0
    companies_skipped_unmatched: int = 0
    companies_skipped_ambiguous: int = 0
    companies_skipped_invalid: int = 0
    apuracoes_received: int = 0
    difal_received: int = 0
    difal_not_found: int = 0
    difal_snapshots_created: int = 0
    difal_snapshots_updated: int = 0
    difal_snapshots_unchanged: int = 0
    fiscal_documents_received: int = 0
    entry_documents_received: int = 0
    exit_documents_received: int = 0
    document_pages_fetched: int = 0
    document_snapshots_created: int = 0
    document_snapshots_updated: int = 0
    document_snapshots_unchanged: int = 0
    tasks_received: int = 0
    task_pages_fetched: int = 0
    tasks_unmatched: int = 0
    task_snapshots_created: int = 0
    task_snapshots_updated: int = 0
    task_snapshots_unchanged: int = 0
    pagination_truncated: bool = False
    context_mismatches: int = 0
    not_found: int = 0
    failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SittaxOperationalSyncResult:
    run: IntegrationSyncRun | None
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    dry_run: bool
    fixture_mode: bool
    status: str


STALE_RUN_MINUTES = 15


def build_fixture_sittax_client(
    *,
    companies_fixture: str | Path | None = None,
    apuracao_fixture: str | Path | None = None,
    difal_fixture: str | Path | None = None,
    entry_documents_fixture: str | Path | None = None,
    exit_documents_fixture: str | Path | None = None,
    tasks_fixture: str | Path | None = None,
) -> FixtureSittaxClient:
    settings = get_settings()
    session = SittaxSession.from_settings(settings)
    return FixtureSittaxClient.from_files(
        session=session,
        login_path=DEFAULT_LOGIN_FIXTURE,
        companies_path=companies_fixture or DEFAULT_COMPANIES_FIXTURE,
        apuracao_path=apuracao_fixture or DEFAULT_APURACAO_FIXTURE,
        difal_path=difal_fixture or DEFAULT_DIFAL_FIXTURE,
        entry_documents_path=entry_documents_fixture or DEFAULT_ENTRY_DOCUMENTS_FIXTURE,
        exit_documents_path=exit_documents_fixture or DEFAULT_EXIT_DOCUMENTS_FIXTURE,
        tasks_path=tasks_fixture or DEFAULT_TASKS_FIXTURE,
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


def sync_sittax_apuracoes(
    session: Session,
    *,
    org_slug: str | None = None,
    organization: Organization | None = None,
    period: str,
    company_id: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    apuracao_fixture: str | Path | None = None,
    client: SittaxClient | FixtureSittaxClient | None = None,
) -> SittaxApuracaoSyncResult:
    if organization is None:
        organization = resolve_target_organization(session, org_slug)

    fiscal_period = _resolve_fiscal_period(session, organization_id=organization.id, period=period)
    fixture_mode = apuracao_fixture is not None
    settings = get_settings()
    created_client = False
    if client is None:
        created_client = True
        client = (
            build_fixture_sittax_client(apuracao_fixture=apuracao_fixture)
            if fixture_mode
            else SittaxClient(session=SittaxSession.from_settings(settings))
        )

    summary = SittaxApuracaoSyncSummary()
    errors: list[dict[str, Any]] = []
    run: IntegrationSyncRun | None = None
    status = "DRY_RUN" if dry_run else "RUNNING"

    candidates = _select_apuracao_candidates(
        session,
        organization_id=organization.id,
        company_id=company_id,
        limit=limit,
        summary=summary,
    )
    summary.companies_selected = len(candidates)

    if not dry_run:
        run = IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="SITTAX",
            job_name="sync_sittax_apuracoes",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            summary={},
            run_metadata={
                "organization_slug": organization.slug,
                "period": period,
                "company_id": company_id,
                "limit": limit,
                "fixture_mode": fixture_mode,
                "dry_run": False,
            },
        )
        session.add(run)
        session.commit()

    try:
        with client.session.exclusive():
            client.authenticate_with_settings(settings)
            for company_snapshot in candidates:
                summary.companies_processed += 1
                try:
                    apuracao = client.get_apuracao(company_cnpj=company_snapshot.cnpj, period=period)
                    summary.apuracoes_received += 1
                except SittaxContextMismatchError as exc:
                    summary.context_mismatches += 1
                    summary.failures += 1
                    errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                    continue
                except Exception as exc:
                    if _is_not_found_error(exc):
                        summary.not_found += 1
                    summary.failures += 1
                    errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                    continue

                if dry_run:
                    continue

                observed_at = datetime.now(timezone.utc)
                snapshot = session.scalar(
                    select(SittaxApuracaoSnapshot).where(
                        SittaxApuracaoSnapshot.organization_id == organization.id,
                        SittaxApuracaoSnapshot.sittax_company_snapshot_id == company_snapshot.id,
                        SittaxApuracaoSnapshot.fiscal_period_id == fiscal_period.id,
                    )
                )
                if snapshot is None:
                    session.add(
                        SittaxApuracaoSnapshot(
                            organization_id=organization.id,
                            sittax_company_snapshot_id=company_snapshot.id,
                            external_company_id=company_snapshot.company_id,
                            fiscal_period_id=fiscal_period.id,
                            sittax_apuracao_id=apuracao.apuracao_id,
                            company_cnpj=company_snapshot.cnpj,
                            company_name=apuracao.company_name,
                            period_reference=period,
                            is_transmitted=apuracao.is_transmitted,
                            transmission_in_progress=apuracao.transmission_in_progress,
                            transmission_type=apuracao.transmission_type,
                            transmitted_at=_normalize_transmitted_at(apuracao.transmitted_at),
                            net_revenue=apuracao.net_revenue,
                            product_revenue=apuracao.product_revenue,
                            service_revenue=apuracao.service_revenue,
                            return_revenue=apuracao.return_revenue,
                            rbt12=apuracao.rbt12,
                            rba=apuracao.rba,
                            das_amount=apuracao.das_amount,
                            das_xml_amount=apuracao.das_xml_amount,
                            factor_r_percent=apuracao.factor_r_percent,
                            company_has_payroll=apuracao.company_has_payroll,
                            taxes_icms=apuracao.taxes_icms,
                            taxes_iss=apuracao.taxes_iss,
                            taxes_ipi=apuracao.taxes_ipi,
                            taxes_pis_cofins=apuracao.taxes_pis_cofins,
                            companies_apuracao=apuracao.companies_apuracao,
                            annexes=apuracao.annexes,
                            cfops=apuracao.cfops,
                            activities=apuracao.activities,
                            payrolls=apuracao.payrolls,
                            alerts=apuracao.alerts,
                            errors=apuracao.errors,
                            risks=apuracao.risks,
                            raw_payload=apuracao.raw_payload,
                            first_seen_at=observed_at,
                            last_seen_at=observed_at,
                        )
                    )
                    session.flush()
                    summary.snapshots_created += 1
                    continue

                changed = _apply_apuracao_snapshot_update(
                    snapshot=snapshot,
                    company_snapshot=company_snapshot,
                    apuracao=apuracao,
                    observed_at=observed_at,
                )
                session.flush()
                if changed:
                    summary.snapshots_updated += 1
                else:
                    summary.snapshots_unchanged += 1

        if not dry_run:
            status = "PARTIAL" if summary.failures > 0 else "SUCCESS"
            assert run is not None
            run.finished_at = datetime.now(timezone.utc)
            run.processed_count = summary.companies_processed
            run.created_count = summary.snapshots_created
            run.updated_count = summary.snapshots_updated
            run.error_count = summary.failures
            run.errors = errors or None
            run.summary = summary.to_dict()
            run.status = status
            session.commit()

        return SittaxApuracaoSyncResult(
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
                    "period": period,
                    "company_id": company_id,
                    "limit": limit,
                    "fixture_mode": fixture_mode,
                    "dry_run": False,
                }
                session.commit()
        raise
    finally:
        if created_client:
            client.close()


def _resolve_fiscal_period(session: Session, *, organization_id: int, period: str) -> FiscalPeriod:
    if period != period.strip() or not INTERFACE_PERIOD_RE.fullmatch(period):
        raise ValueError("Period must use YYYY-MM format.")
    month = int(period[5:7])
    if month < 1 or month > 12:
        raise ValueError("Period must contain a valid month.")
    fiscal_period = session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.organization_id == organization_id,
            FiscalPeriod.competencia == period,
        )
    )
    if fiscal_period is None:
        raise ValueError(f"Fiscal period '{period}' was not found for this organization.")
    return fiscal_period


def _select_apuracao_candidates(
    session: Session,
    *,
    organization_id: int,
    company_id: int | None,
    limit: int | None,
    summary: SittaxApuracaoSyncSummary,
) -> list[SittaxCompanySnapshot]:
    if limit is not None and limit <= 0:
        raise ValueError("Limit must be greater than zero.")

    if company_id is not None:
        company_snapshot = session.scalar(
            select(SittaxCompanySnapshot).where(
                SittaxCompanySnapshot.organization_id == organization_id,
                SittaxCompanySnapshot.company_id == company_id,
                SittaxCompanySnapshot.match_status == MATCHED,
            )
        )
        if company_snapshot is None:
            raise ValueError(f"Matched Sittax company snapshot not found for company_id={company_id}.")
        return [company_snapshot]

    rows = session.scalars(
        select(SittaxCompanySnapshot)
        .where(SittaxCompanySnapshot.organization_id == organization_id)
        .order_by(SittaxCompanySnapshot.id.asc())
    ).all()

    matched: list[SittaxCompanySnapshot] = []
    for row in rows:
        if row.match_status == MATCHED:
            matched.append(row)
        elif row.match_status == UNMATCHED:
            summary.companies_skipped_unmatched += 1
        elif row.match_status == AMBIGUOUS:
            summary.companies_skipped_ambiguous += 1
        elif row.match_status == INVALID_CNPJ:
            summary.companies_skipped_invalid += 1
    return matched[:limit] if limit is not None else matched


def _apply_apuracao_snapshot_update(
    *,
    snapshot: SittaxApuracaoSnapshot,
    company_snapshot: SittaxCompanySnapshot,
    apuracao,
    observed_at: datetime,
) -> bool:
    changed = False
    updates = {
        "external_company_id": company_snapshot.company_id,
        "sittax_apuracao_id": apuracao.apuracao_id,
        "company_cnpj": company_snapshot.cnpj,
        "company_name": apuracao.company_name,
        "period_reference": apuracao.confirmed_period,
        "is_transmitted": apuracao.is_transmitted,
        "transmission_in_progress": apuracao.transmission_in_progress,
        "transmission_type": apuracao.transmission_type,
        "transmitted_at": _normalize_transmitted_at(apuracao.transmitted_at),
        "net_revenue": apuracao.net_revenue,
        "product_revenue": apuracao.product_revenue,
        "service_revenue": apuracao.service_revenue,
        "return_revenue": apuracao.return_revenue,
        "rbt12": apuracao.rbt12,
        "rba": apuracao.rba,
        "das_amount": apuracao.das_amount,
        "das_xml_amount": apuracao.das_xml_amount,
        "factor_r_percent": apuracao.factor_r_percent,
        "company_has_payroll": apuracao.company_has_payroll,
        "taxes_icms": apuracao.taxes_icms,
        "taxes_iss": apuracao.taxes_iss,
        "taxes_ipi": apuracao.taxes_ipi,
        "taxes_pis_cofins": apuracao.taxes_pis_cofins,
        "companies_apuracao": apuracao.companies_apuracao,
        "annexes": apuracao.annexes,
        "cfops": apuracao.cfops,
        "activities": apuracao.activities,
        "payrolls": apuracao.payrolls,
        "alerts": apuracao.alerts,
        "errors": apuracao.errors,
        "risks": apuracao.risks,
        "raw_payload": apuracao.raw_payload,
    }
    for field, value in updates.items():
        if getattr(snapshot, field) != value:
            setattr(snapshot, field, value)
            changed = True
    snapshot.last_seen_at = observed_at
    return changed


def _normalize_transmitted_at(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if "." in normalized:
        prefix, suffix = normalized.split(".", 1)
        timezone_part = ""
        fraction_part = suffix
        for marker in ("+", "-"):
            marker_index = suffix.find(marker)
            if marker_index > 0:
                fraction_part = suffix[:marker_index]
                timezone_part = suffix[marker_index:]
                break
        if fraction_part:
            fraction_part = f"{fraction_part[:6]:0<6}"
        if len(fraction_part) > 6:
            fraction_part = fraction_part[:6]
        normalized = f"{prefix}.{fraction_part}{timezone_part}"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_company_error(company_snapshot: SittaxCompanySnapshot, *, period: str, error: Exception) -> dict[str, Any]:
    payload = {
        "scope": "company",
        "company_id": company_snapshot.company_id,
        "snapshot_id": company_snapshot.id,
        "company_cnpj": mask_value(company_snapshot.cnpj),
        "period": period,
        "error": error.__class__.__name__,
    }
    diagnostic = getattr(error, "diagnostic", None)
    if isinstance(diagnostic, dict):
        payload["contract"] = diagnostic
    return payload


def _is_not_found_error(error: Exception) -> bool:
    return isinstance(error, SittaxResponseError) and "404" in str(error)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _strip_contract_diagnostics(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped: list[dict[str, Any]] = []
    for error in errors:
        normalized = {key: value for key, value in error.items() if key != "contract"}
        stripped.append(normalized)
    return stripped


def _finalize_sync_run(
    session: Session,
    *,
    run_id: int,
    status: str,
    processed_count: int,
    created_count: int,
    updated_count: int,
    error_count: int,
    errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    run = session.get(IntegrationSyncRun, run_id)
    if run is None:
        return
    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.processed_count = processed_count
    run.created_count = created_count
    run.updated_count = updated_count
    run.error_count = error_count
    run.errors = _json_safe(_strip_contract_diagnostics(errors)) or None
    run.summary = _json_safe(summary)
    session.commit()


def build_finalize_run_27_sql() -> str:
    return (
        "update integration_sync_runs "
        "set status = 'FAILED', finished_at = now(), error_count = 1, "
        "run_metadata = coalesce(run_metadata, '{}'::jsonb) || "
        """'{"stale_local_validation_run": true}'::jsonb """
        "where id = 27 and provider = 'SITTAX' and job_name = 'sync_sittax_operational' and finished_at is null;"
    )


def sync_sittax_operational(
    session: Session,
    *,
    org_slug: str | None = None,
    organization: Organization | None = None,
    period: str,
    company_id: int | None = None,
    limit: int | None = None,
    scope: str = "ALL",
    max_pages: int = 100,
    dry_run: bool = False,
    difal_fixture: str | Path | None = None,
    entry_documents_fixture: str | Path | None = None,
    exit_documents_fixture: str | Path | None = None,
    tasks_fixture: str | Path | None = None,
    apuracao_fixture: str | Path | None = None,
    diagnostic_contract: bool = False,
    client: SittaxClient | FixtureSittaxClient | None = None,
) -> SittaxOperationalSyncResult:
    if organization is None:
        organization = resolve_target_organization(session, org_slug)
    normalized_scope = scope.strip().upper()
    if normalized_scope not in {"ALL", "DIFAL", "DOCUMENTS", "TASKS"}:
        raise ValueError("Scope must be one of ALL, DIFAL, DOCUMENTS or TASKS.")
    if max_pages <= 0:
        raise ValueError("max_pages must be greater than zero.")

    fiscal_period = _resolve_fiscal_period(session, organization_id=organization.id, period=period)
    settings = get_settings()
    fixture_mode = any(
        fixture is not None
        for fixture in (difal_fixture, entry_documents_fixture, exit_documents_fixture, tasks_fixture, apuracao_fixture)
    )
    created_client = False
    if client is None:
        created_client = True
        client = (
            build_fixture_sittax_client(
                apuracao_fixture=apuracao_fixture,
                difal_fixture=difal_fixture,
                entry_documents_fixture=entry_documents_fixture,
                exit_documents_fixture=exit_documents_fixture,
                tasks_fixture=tasks_fixture,
            )
            if fixture_mode
            else SittaxClient(session=SittaxSession.from_settings(settings))
        )

    summary = SittaxOperationalSyncSummary()
    errors: list[dict[str, Any]] = []
    status = "DRY_RUN" if dry_run else "RUNNING"
    run: IntegrationSyncRun | None = None
    if normalized_scope == "TASKS":
        candidates: list[SittaxCompanySnapshot] = []
    else:
        candidates = _select_apuracao_candidates(
            session,
            organization_id=organization.id,
            company_id=company_id,
            limit=limit,
            summary=summary,  # type: ignore[arg-type]
        )
        summary.companies_selected = len(candidates)

    if not dry_run:
        run = IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="SITTAX",
            job_name="sync_sittax_operational",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            summary={},
            run_metadata={
                "organization_slug": organization.slug,
                "period": period,
                "company_id": company_id,
                "limit": limit,
                "scope": normalized_scope,
                "max_pages": max_pages,
                "fixture_mode": fixture_mode,
                "dry_run": False,
            },
        )
        session.add(run)
        session.commit()

    try:
        with client.session.exclusive():
            client.authenticate_with_settings(settings)

            if normalized_scope != "TASKS":
                for company_snapshot in candidates:
                    summary.companies_processed += 1
                    try:
                        apuracao = client.get_apuracao(company_cnpj=company_snapshot.cnpj, period=period)
                        summary.apuracoes_received += 1
                    except SittaxContextMismatchError as exc:
                        summary.context_mismatches += 1
                        summary.failures += 1
                        errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                        continue
                    except Exception as exc:
                        if _is_not_found_error(exc):
                            summary.not_found += 1
                        summary.failures += 1
                        errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                        continue

                    observed_at = datetime.now(timezone.utc)
                    apuracao_snapshot = None if dry_run else _upsert_apuracao_for_operational_sync(
                        session=session,
                        organization_id=organization.id,
                        company_snapshot=company_snapshot,
                        fiscal_period=fiscal_period,
                        apuracao=apuracao,
                        observed_at=observed_at,
                    )

                    company_errors_before = len(errors)
                    if normalized_scope in {"ALL", "DIFAL", "DOCUMENTS"}:
                        try:
                            client.ensure_api_context(company_cnpj=company_snapshot.cnpj, period=period)
                        except Exception as exc:
                            if isinstance(exc, SittaxContextMismatchError) or exc.__class__.__name__ == "SittaxContextMismatchError":
                                summary.context_mismatches += 1
                            summary.failures += 1
                            errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                            continue

                    if normalized_scope in {"ALL", "DIFAL"}:
                        try:
                            difal = client.get_difal(company_cnpj=company_snapshot.cnpj, period=period)
                            summary.difal_received += 1
                            if not dry_run and apuracao_snapshot is not None:
                                created, updated = _upsert_difal_snapshot(
                                    session=session,
                                    organization_id=organization.id,
                                    company_snapshot=company_snapshot,
                                    apuracao_snapshot=apuracao_snapshot,
                                    fiscal_period=fiscal_period,
                                    difal=difal,
                                    company_cnpj=company_snapshot.cnpj,
                                    period=period,
                                    observed_at=observed_at,
                                )
                                if created:
                                    summary.difal_snapshots_created += 1
                                elif updated:
                                    summary.difal_snapshots_updated += 1
                                else:
                                    summary.difal_snapshots_unchanged += 1
                        except Exception as exc:
                            if _is_not_found_error(exc):
                                summary.difal_not_found += 1
                            elif isinstance(exc, SittaxContextMismatchError) or exc.__class__.__name__ == "SittaxContextMismatchError":
                                summary.context_mismatches += 1
                                summary.failures += 1
                            else:
                                summary.failures += 1
                            errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                            continue

                    if normalized_scope in {"ALL", "DOCUMENTS"}:
                        for direction in ("ENTRADA", "SAIDA"):
                            try:
                                pages = client.paginate_fiscal_documents(
                                    company_cnpj=company_snapshot.cnpj,
                                    period=period,
                                    direction=direction,
                                    max_pages=max_pages,
                                )
                            except SittaxPaginationError as exc:
                                summary.pagination_truncated = True
                                summary.failures += 1
                                errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                                break
                            except Exception as exc:
                                if isinstance(exc, SittaxContextMismatchError) or exc.__class__.__name__ == "SittaxContextMismatchError":
                                    summary.context_mismatches += 1
                                    summary.failures += 1
                                else:
                                    summary.failures += 1
                                errors.append(_build_company_error(company_snapshot, period=period, error=exc))
                                break

                            summary.document_pages_fetched += len(pages)
                            for page in pages:
                                summary.fiscal_documents_received += len(page.items)
                                if direction == "ENTRADA":
                                    summary.entry_documents_received += len(page.items)
                                else:
                                    summary.exit_documents_received += len(page.items)
                                if dry_run or apuracao_snapshot is None:
                                    continue
                                for item in page.items:
                                    created, updated = _upsert_document_snapshot(
                                        session=session,
                                        organization_id=organization.id,
                                        company_snapshot=company_snapshot,
                                        apuracao_snapshot=apuracao_snapshot,
                                        fiscal_period=fiscal_period,
                                        document=item,
                                        observed_at=observed_at,
                                    )
                                    if created:
                                        summary.document_snapshots_created += 1
                                    elif updated:
                                        summary.document_snapshots_updated += 1
                                    else:
                                        summary.document_snapshots_unchanged += 1
                        client.session.clear_active_context()

                    if len(errors) > company_errors_before and diagnostic_contract:
                        errors[-1] = _json_safe(errors[-1])

            if normalized_scope in {"ALL", "TASKS"}:
                try:
                    task_pages = client.paginate_tasks(max_pages=max_pages)
                    summary.task_pages_fetched = len(task_pages)
                    for page in task_pages:
                        summary.tasks_received += len(page.items)
                        if dry_run:
                            continue
                        for task in page.items:
                            created, updated, unmatched = _upsert_task_snapshot(
                                session=session,
                                organization_id=organization.id,
                                fiscal_period=fiscal_period,
                                task=task,
                                observed_at=datetime.now(timezone.utc),
                            )
                            if unmatched:
                                summary.tasks_unmatched += 1
                            if created:
                                summary.task_snapshots_created += 1
                            elif updated:
                                summary.task_snapshots_updated += 1
                            else:
                                summary.task_snapshots_unchanged += 1
                except SittaxPaginationError as exc:
                    summary.pagination_truncated = True
                    summary.failures += 1
                    errors.append({"scope": "tasks", "error": exc.__class__.__name__})

        if not dry_run:
            status = "PARTIAL" if summary.failures > 0 or summary.pagination_truncated else "SUCCESS"
            assert run is not None
            _finalize_sync_run(
                session,
                run_id=run.id,
                status=status,
                processed_count=summary.companies_processed,
                created_count=summary.difal_snapshots_created
                + summary.document_snapshots_created
                + summary.task_snapshots_created,
                updated_count=summary.difal_snapshots_updated
                + summary.document_snapshots_updated
                + summary.task_snapshots_updated,
                error_count=summary.failures,
                errors=errors,
                summary=summary.to_dict(),
            )

        return SittaxOperationalSyncResult(
            run=run,
            summary=_json_safe(summary.to_dict()),
            errors=errors if diagnostic_contract else _strip_contract_diagnostics(errors),
            dry_run=dry_run,
            fixture_mode=fixture_mode,
            status=status,
        )
    except Exception as exc:
        if not dry_run and run is not None:
            session.rollback()
            try:
                _finalize_sync_run(
                    session,
                    run_id=run.id,
                    status="FAILED",
                    processed_count=summary.companies_processed,
                    created_count=summary.difal_snapshots_created
                    + summary.document_snapshots_created
                    + summary.task_snapshots_created,
                    updated_count=summary.difal_snapshots_updated
                    + summary.document_snapshots_updated
                    + summary.task_snapshots_updated,
                    error_count=max(summary.failures, 1),
                    errors=errors + [{"scope": "global", "error": exc.__class__.__name__}],
                    summary=summary.to_dict(),
                )
            except Exception:
                session.rollback()
        raise
    finally:
        if created_client:
            client.close()


def _upsert_apuracao_for_operational_sync(
    *,
    session: Session,
    organization_id: int,
    company_snapshot: SittaxCompanySnapshot,
    fiscal_period: FiscalPeriod,
    apuracao,
    observed_at: datetime,
) -> SittaxApuracaoSnapshot:
    snapshot = session.scalar(
        select(SittaxApuracaoSnapshot).where(
            SittaxApuracaoSnapshot.organization_id == organization_id,
            SittaxApuracaoSnapshot.sittax_company_snapshot_id == company_snapshot.id,
            SittaxApuracaoSnapshot.fiscal_period_id == fiscal_period.id,
        )
    )
    if snapshot is None:
        snapshot = SittaxApuracaoSnapshot(
            organization_id=organization_id,
            sittax_company_snapshot_id=company_snapshot.id,
            external_company_id=company_snapshot.company_id,
            fiscal_period_id=fiscal_period.id,
            sittax_apuracao_id=apuracao.apuracao_id,
            company_cnpj=company_snapshot.cnpj,
            company_name=apuracao.company_name,
            period_reference=apuracao.confirmed_period,
            is_transmitted=apuracao.is_transmitted,
            transmission_in_progress=apuracao.transmission_in_progress,
            transmission_type=apuracao.transmission_type,
            transmitted_at=_normalize_transmitted_at(apuracao.transmitted_at),
            net_revenue=apuracao.net_revenue,
            product_revenue=apuracao.product_revenue,
            service_revenue=apuracao.service_revenue,
            return_revenue=apuracao.return_revenue,
            rbt12=apuracao.rbt12,
            rba=apuracao.rba,
            das_amount=apuracao.das_amount,
            das_xml_amount=apuracao.das_xml_amount,
            factor_r_percent=apuracao.factor_r_percent,
            company_has_payroll=apuracao.company_has_payroll,
            taxes_icms=apuracao.taxes_icms,
            taxes_iss=apuracao.taxes_iss,
            taxes_ipi=apuracao.taxes_ipi,
            taxes_pis_cofins=apuracao.taxes_pis_cofins,
            companies_apuracao=apuracao.companies_apuracao,
            annexes=apuracao.annexes,
            cfops=apuracao.cfops,
            activities=apuracao.activities,
            payrolls=apuracao.payrolls,
            alerts=apuracao.alerts,
            errors=apuracao.errors,
            risks=apuracao.risks,
            raw_payload=apuracao.raw_payload,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        session.add(snapshot)
        session.flush()
        return snapshot
    _apply_apuracao_snapshot_update(
        snapshot=snapshot,
        company_snapshot=company_snapshot,
        apuracao=apuracao,
        observed_at=observed_at,
    )
    session.flush()
    return snapshot


def _upsert_difal_snapshot(
    *,
    session: Session,
    organization_id: int,
    company_snapshot: SittaxCompanySnapshot,
    apuracao_snapshot: SittaxApuracaoSnapshot,
    fiscal_period: FiscalPeriod,
    difal,
    company_cnpj: str,
    period: str,
    observed_at: datetime,
) -> tuple[bool, bool]:
    snapshot = session.scalar(
        select(SittaxDifalSnapshot).where(
            SittaxDifalSnapshot.organization_id == organization_id,
            SittaxDifalSnapshot.sittax_company_snapshot_id == company_snapshot.id,
            SittaxDifalSnapshot.fiscal_period_id == fiscal_period.id,
        )
    )
    if snapshot is None:
        session.add(
            SittaxDifalSnapshot(
                organization_id=organization_id,
                sittax_company_snapshot_id=company_snapshot.id,
                sittax_apuracao_snapshot_id=apuracao_snapshot.id,
                external_company_id=company_snapshot.company_id,
                fiscal_period_id=fiscal_period.id,
                company_cnpj=company_cnpj,
                period_reference=period,
                has_guide=difal.has_guide,
                dare_numbers=difal.dare_numbers,
                total_amount=difal.total_amount,
                resale_amount=difal.resale_amount,
                use_consumption_fixed_asset_amount=difal.use_consumption_fixed_asset_amount,
                closing_date=_normalize_transmitted_at(difal.closing_date),
                transmission_date=_normalize_transmitted_at(difal.transmission_date),
                total_purchases=difal.total_purchases,
                message=difal.message,
                notes_without_type_or_reference=difal.notes_without_type_or_reference,
                inconsistencies=difal.inconsistencies,
                raw_payload=difal.raw_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
        )
        session.flush()
        return True, False
    changed = False
    updates = {
        "sittax_apuracao_snapshot_id": apuracao_snapshot.id,
        "external_company_id": company_snapshot.company_id,
        "company_cnpj": company_cnpj,
        "period_reference": period,
        "has_guide": difal.has_guide,
        "dare_numbers": difal.dare_numbers,
        "total_amount": difal.total_amount,
        "resale_amount": difal.resale_amount,
        "use_consumption_fixed_asset_amount": difal.use_consumption_fixed_asset_amount,
        "closing_date": _normalize_transmitted_at(difal.closing_date),
        "transmission_date": _normalize_transmitted_at(difal.transmission_date),
        "total_purchases": difal.total_purchases,
        "message": difal.message,
        "notes_without_type_or_reference": difal.notes_without_type_or_reference,
        "inconsistencies": difal.inconsistencies,
        "raw_payload": difal.raw_payload,
    }
    for field, value in updates.items():
        if getattr(snapshot, field) != value:
            setattr(snapshot, field, value)
            changed = True
    snapshot.last_seen_at = observed_at
    session.flush()
    return False, changed


def _upsert_document_snapshot(
    *,
    session: Session,
    organization_id: int,
    company_snapshot: SittaxCompanySnapshot,
    apuracao_snapshot: SittaxApuracaoSnapshot,
    fiscal_period: FiscalPeriod,
    document,
    observed_at: datetime,
) -> tuple[bool, bool]:
    snapshot = session.scalar(
        select(SittaxFiscalDocumentSnapshot).where(
            SittaxFiscalDocumentSnapshot.organization_id == organization_id,
            SittaxFiscalDocumentSnapshot.sittax_company_snapshot_id == company_snapshot.id,
            SittaxFiscalDocumentSnapshot.document_direction == document.document_direction,
            SittaxFiscalDocumentSnapshot.source_document_key == document.source_document_key,
        )
    )
    if snapshot is None:
        session.add(
            SittaxFiscalDocumentSnapshot(
                organization_id=organization_id,
                sittax_company_snapshot_id=company_snapshot.id,
                sittax_apuracao_snapshot_id=apuracao_snapshot.id,
                external_company_id=company_snapshot.company_id,
                fiscal_period_id=fiscal_period.id,
                source_document_key=document.source_document_key,
                sittax_document_id=document.sittax_document_id,
                document_direction=document.document_direction,
                access_key=document.access_key,
                model=document.model,
                document_number=document.document_number,
                status=document.status,
                issue_date=_normalize_transmitted_at(document.issue_date),
                entry_date=_normalize_transmitted_at(document.entry_date),
                period_reference=document.period_reference,
                issuer_name=document.issuer_name,
                issuer_state=document.issuer_state,
                recipient_name=document.recipient_name,
                recipient_state=document.recipient_state,
                issuer_document=document.issuer_document,
                cfops=document.cfops,
                total_amount=document.total_amount,
                import_source=document.import_source,
                imported=document.imported,
                has_xml=document.has_xml,
                raw_payload=document.raw_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
        )
        session.flush()
        return True, False
    changed = False
    updates = {
        "sittax_apuracao_snapshot_id": apuracao_snapshot.id,
        "external_company_id": company_snapshot.company_id,
        "fiscal_period_id": fiscal_period.id,
        "sittax_document_id": document.sittax_document_id,
        "access_key": document.access_key,
        "model": document.model,
        "document_number": document.document_number,
        "status": document.status,
        "issue_date": _normalize_transmitted_at(document.issue_date),
        "entry_date": _normalize_transmitted_at(document.entry_date),
        "period_reference": document.period_reference,
        "issuer_name": document.issuer_name,
        "issuer_state": document.issuer_state,
        "recipient_name": document.recipient_name,
        "recipient_state": document.recipient_state,
        "issuer_document": document.issuer_document,
        "cfops": document.cfops,
        "total_amount": document.total_amount,
        "import_source": document.import_source,
        "imported": document.imported,
        "has_xml": document.has_xml,
        "raw_payload": document.raw_payload,
    }
    for field, value in updates.items():
        if getattr(snapshot, field) != value:
            setattr(snapshot, field, value)
            changed = True
    snapshot.last_seen_at = observed_at
    session.flush()
    return False, changed


def _upsert_task_snapshot(
    *,
    session: Session,
    organization_id: int,
    fiscal_period: FiscalPeriod,
    task,
    observed_at: datetime,
) -> tuple[bool, bool, bool]:
    company_snapshot = None
    external_company_id = None
    unmatched = False
    if task.company_cnpj is not None:
        company_snapshot = session.scalar(
            select(SittaxCompanySnapshot).where(
                SittaxCompanySnapshot.organization_id == organization_id,
                SittaxCompanySnapshot.cnpj == task.company_cnpj,
            )
        )
        if company_snapshot is not None:
            external_company_id = company_snapshot.company_id
        else:
            unmatched = True

    snapshot = session.scalar(
        select(SittaxTaskSnapshot).where(
            SittaxTaskSnapshot.organization_id == organization_id,
            SittaxTaskSnapshot.source_task_key == task.source_task_key,
        )
    )
    if snapshot is None:
        session.add(
            SittaxTaskSnapshot(
                organization_id=organization_id,
                source_task_key=task.source_task_key,
                sittax_task_id=task.sittax_task_id,
                sittax_company_snapshot_id=company_snapshot.id if company_snapshot is not None else None,
                external_company_id=external_company_id,
                fiscal_period_id=fiscal_period.id if task.period_reference == fiscal_period.competencia else None,
                task_type=task.task_type,
                task_name=task.task_name,
                description=task.description,
                company_name=task.company_name,
                company_cnpj=task.company_cnpj,
                period_reference=task.period_reference,
                source_created_at=_normalize_transmitted_at(task.source_created_at),
                source_finished_at=_normalize_transmitted_at(task.source_finished_at),
                source_user_id=task.source_user_id,
                source_user_name=task.source_user_name,
                status=task.status,
                status_code=task.status_code,
                has_file=task.has_file,
                file_name=task.file_name,
                file_extension=task.file_extension,
                file_extension_code=task.file_extension_code,
                processing_time_seconds=task.processing_time_seconds,
                raw_payload=task.raw_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
        )
        session.flush()
        return True, False, unmatched
    changed = False
    updates = {
        "sittax_task_id": task.sittax_task_id,
        "sittax_company_snapshot_id": company_snapshot.id if company_snapshot is not None else None,
        "external_company_id": external_company_id,
        "fiscal_period_id": fiscal_period.id if task.period_reference == fiscal_period.competencia else None,
        "task_type": task.task_type,
        "task_name": task.task_name,
        "description": task.description,
        "company_name": task.company_name,
        "company_cnpj": task.company_cnpj,
        "period_reference": task.period_reference,
        "source_created_at": _normalize_transmitted_at(task.source_created_at),
        "source_finished_at": _normalize_transmitted_at(task.source_finished_at),
        "source_user_id": task.source_user_id,
        "source_user_name": task.source_user_name,
        "status": task.status,
        "status_code": task.status_code,
        "has_file": task.has_file,
        "file_name": task.file_name,
        "file_extension": task.file_extension,
        "file_extension_code": task.file_extension_code,
        "processing_time_seconds": task.processing_time_seconds,
        "raw_payload": task.raw_payload,
    }
    for field, value in updates.items():
        if getattr(snapshot, field) != value:
            setattr(snapshot, field, value)
            changed = True
    snapshot.last_seen_at = observed_at
    session.flush()
    return False, changed, unmatched
