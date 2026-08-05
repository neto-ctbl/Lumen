from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.services.integrations.acessorias.sync import (
    AcessoriasSyncSummary,
    FixtureAcessoriasClient,
    sync_acessorias_companies,
    sync_acessorias_period,
)
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


@dataclass(slots=True)
class AcessoriasBackfillResult:
    status: str
    dry_run: bool
    summary: dict[str, Any]
    period_summaries: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    run_ids: list[int]


def build_fixture_acessorias_client(
    *,
    companies_fixture: str | None,
    deliveries_fixture: str | None = None,
    deliveries_fixture_dir: str | None = None,
) -> FixtureAcessoriasClient | None:
    if not companies_fixture and not deliveries_fixture and not deliveries_fixture_dir:
        return None
    if not companies_fixture:
        raise ValueError("--companies-fixture is required when fixture mode is enabled.")
    if deliveries_fixture and deliveries_fixture_dir:
        raise ValueError("Use either --deliveries-fixture or --deliveries-fixture-dir, not both.")
    if deliveries_fixture_dir:
        return FixtureAcessoriasClient.from_directory(
            companies_path=companies_fixture,
            deliveries_dir=deliveries_fixture_dir,
        )
    if not deliveries_fixture:
        raise ValueError("--deliveries-fixture or --deliveries-fixture-dir is required in fixture mode.")
    return FixtureAcessoriasClient.from_files(
        companies_path=companies_fixture,
        deliveries_path=deliveries_fixture,
    )


def validate_period(period: str) -> tuple[int, int]:
    if period != period.strip() or not PERIOD_RE.fullmatch(period):
        raise ValueError("Period must use YYYY-MM format.")
    year = int(period[:4])
    month = int(period[5:7])
    if month < 1 or month > 12:
        raise ValueError("Period must contain a valid month.")
    return year, month


def iter_period_range(from_period: str, to_period: str) -> list[str]:
    from_year, from_month = validate_period(from_period)
    to_year, to_month = validate_period(to_period)
    if (from_year, from_month) > (to_year, to_month):
        raise ValueError("from-period cannot be later than to-period.")

    periods: list[str] = []
    year = from_year
    month = from_month
    while (year, month) <= (to_year, to_month):
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return periods


def backfill_acessorias(
    session: Session,
    *,
    org_slug: str | None = None,
    organization: Organization | None = None,
    from_period: str,
    to_period: str,
    company_id: int | None = None,
    dry_run: bool = False,
    skip_companies: bool = False,
    only_active: bool = True,
    fiscal_only: bool = False,
    stop_on_error: bool = False,
    client: Any | None = None,
) -> AcessoriasBackfillResult:
    periods_requested = iter_period_range(from_period, to_period)
    if organization is None:
        organization = resolve_target_organization(session, org_slug)

    if company_id is not None:
        company = session.scalar(
            select(ExternalCompany).where(
                ExternalCompany.organization_id == organization.id,
                ExternalCompany.id == company_id,
            )
        )
        if company is None:
            raise ValueError(f"Company '{company_id}' was not found for organization '{organization.slug}'.")

    period_rows = session.scalars(
        select(FiscalPeriod).where(
            FiscalPeriod.organization_id == organization.id,
            FiscalPeriod.competencia.in_(periods_requested),
        )
    ).all()
    period_map = {row.competencia: row for row in period_rows}
    periods_missing = [period for period in periods_requested if period not in period_map]
    if periods_missing:
        raise ValueError(
            "Missing fiscal periods for organization "
            f"'{organization.slug}': {', '.join(periods_missing)}."
        )

    if client is None:
        from backend.app.core.config import get_settings
        from backend.app.services.integrations.acessorias.client import AcessoriasClient

        client = AcessoriasClient.from_settings(get_settings())

    aggregate = {
        "periods_requested": len(periods_requested),
        "periods_found": len(periods_requested),
        "periods_missing": [],
        "periods_processed": 0,
        "periods_success": 0,
        "periods_partial": 0,
        "periods_failed": 0,
        "companies_received": 0,
        "companies_matched": 0,
        "companies_unmatched": 0,
        "regimes_mapped": 0,
        "regimes_unmapped": 0,
        "deliveries_received": 0,
        "delivery_snapshots_created": 0,
        "delivery_snapshots_updated": 0,
        "statuses_created": 0,
        "statuses_updated": 0,
        "tasks_skipped": 0,
        "deliveries_filtered_out": 0,
        "unmapped_obligations": 0,
        "manual_review": 0,
        "failures": 0,
        "unknown_obligation_names": {},
    }
    errors: list[dict[str, Any]] = []
    period_summaries: list[dict[str, Any]] = []
    run_ids: list[int] = []

    if not skip_companies:
        company_summary = AcessoriasSyncSummary()
        company_errors: list[dict[str, Any]] = []
        try:
            sync_acessorias_companies(
                session,
                organization=organization,
                client=client,
                dry_run=dry_run,
                summary=company_summary,
                errors=company_errors,
            )
            if dry_run:
                session.rollback()
            else:
                session.commit()
        except Exception as exc:
            if not dry_run:
                session.rollback()
            company_errors.append({"scope": "companies_phase", "error": str(exc)})
            company_summary.failures += 1
            if stop_on_error:
                raise

        _merge_summary(aggregate, sanitize_sync_summary(company_summary.to_dict()))
        errors.extend(company_errors)

    for period in periods_requested:
        aggregate["periods_processed"] += 1
        try:
            result = sync_acessorias_period(
                session,
                period=period,
                organization=organization,
                company_id=company_id,
                dry_run=dry_run,
                sync_companies=False,
                sync_deliveries=True,
                only_active=only_active,
                fiscal_only=fiscal_only,
                run_metadata_extra={
                    "backfill": True,
                    "from_period": from_period,
                    "to_period": to_period,
                    "current_period": period,
                    "dry_run": dry_run,
                    "fiscal_only": fiscal_only,
                },
                client=client,
            )
        except Exception as exc:
            session.rollback()
            aggregate["periods_failed"] += 1
            aggregate["failures"] += 1
            error = {"scope": "period", "period": period, "error": str(exc)}
            errors.append(error)
            period_summaries.append(
                {
                    "period": period,
                    "status": "FAILED",
                    "run_id": None,
                    "summary": {"failures": 1},
                    "errors": 1,
                }
            )
            if stop_on_error:
                raise
            continue

        if result.run is not None:
            run_ids.append(result.run.id)
        sanitized_summary = sanitize_sync_summary(result.summary)
        _merge_summary(aggregate, sanitized_summary)
        errors.extend(result.errors)
        period_status = _resolve_period_status(result, sanitized_summary)
        if period_status == "SUCCESS":
            aggregate["periods_success"] += 1
        elif period_status == "PARTIAL":
            aggregate["periods_partial"] += 1
        else:
            aggregate["periods_failed"] += 1
        period_summaries.append(
            {
                "period": period,
                "status": period_status,
                "run_id": result.run.id if result.run is not None else None,
                "summary": sanitized_summary,
                "errors": len(result.errors),
            }
        )
        if stop_on_error and period_status != "SUCCESS":
            raise RuntimeError(f"Backfill stopped after period '{period}' finished with status '{period_status}'.")

    status = "SUCCESS"
    if aggregate["periods_failed"] > 0 and aggregate["periods_success"] == 0 and aggregate["periods_partial"] == 0:
        status = "FAILED"
    elif aggregate["periods_failed"] > 0 or aggregate["periods_partial"] > 0 or aggregate["failures"] > 0:
        status = "PARTIAL"
    if dry_run:
        session.rollback()

    return AcessoriasBackfillResult(
        status=status,
        dry_run=dry_run,
        summary=aggregate,
        period_summaries=period_summaries,
        errors=errors,
        run_ids=run_ids,
    )


def sanitize_sync_summary(summary: dict[str, Any]) -> dict[str, Any]:
    sanitized = {key: value for key, value in summary.items() if key != "affected_companies_for_unmapped"}
    unknown_names = sanitized.get("unknown_obligation_names")
    if isinstance(unknown_names, dict):
        sanitized["unknown_obligation_names"] = dict(sorted(unknown_names.items()))
    return sanitized


def _merge_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key == "unknown_obligation_names" and isinstance(value, dict):
            bucket = target.setdefault(key, {})
            for name, count in value.items():
                bucket[name] = bucket.get(name, 0) + count
            continue
        if key in target and isinstance(target[key], int) and isinstance(value, int):
            target[key] += value


def _resolve_period_status(result: Any, summary: dict[str, Any]) -> str:
    if result.run is not None:
        return result.run.status
    processed = int(summary.get("deliveries_received", 0))
    failures = int(summary.get("failures", 0))
    if processed == 0 and failures == 0:
        return "FAILED"
    if failures > 0:
        return "PARTIAL"
    return "SUCCESS"
