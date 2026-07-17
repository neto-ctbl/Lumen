from __future__ import annotations

from dataclasses import dataclass
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
from backend.app.services.integrations.econtrole.sync import resolve_target_organization

from .client import FixtureSittaxClient, SittaxClient
from .errors import SittaxContextMismatchError, SittaxResponseError
from .mapper import map_company_item
from .session import SittaxSession


FIXTURE_DIR = Path("backend/tests/fixtures/sittax")
DEFAULT_LOGIN_FIXTURE = FIXTURE_DIR / "login_success.json"
DEFAULT_COMPANIES_FIXTURE = FIXTURE_DIR / "companies_success.json"
DEFAULT_APURACAO_FIXTURE = FIXTURE_DIR / "apuracao_success.json"
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


def build_fixture_sittax_client(
    *,
    companies_fixture: str | Path | None = None,
    apuracao_fixture: str | Path | None = None,
) -> FixtureSittaxClient:
    settings = get_settings()
    session = SittaxSession.from_settings(settings)
    return FixtureSittaxClient.from_files(
        session=session,
        login_path=DEFAULT_LOGIN_FIXTURE,
        companies_path=companies_fixture or DEFAULT_COMPANIES_FIXTURE,
        apuracao_path=apuracao_fixture or DEFAULT_APURACAO_FIXTURE,
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
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_company_error(company_snapshot: SittaxCompanySnapshot, *, period: str, error: Exception) -> dict[str, Any]:
    return {
        "scope": "company",
        "company_id": company_snapshot.company_id,
        "snapshot_id": company_snapshot.id,
        "company_cnpj": mask_value(company_snapshot.cnpj),
        "period": period,
        "error": error.__class__.__name__,
    }


def _is_not_found_error(error: Exception) -> bool:
    return isinstance(error, SittaxResponseError) and "404" in str(error)
