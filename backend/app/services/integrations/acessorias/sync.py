from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import ReconciliationStatus
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.acessorias_delivery_snapshot import AcessoriasDeliverySnapshot
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.integration_sync_run import IntegrationSyncRun
from backend.app.models.organization import Organization
from backend.app.services.audit import record_audit_event
from backend.app.services.integrations.acessorias.client import (
    AcessoriasClient,
)
from backend.app.services.integrations.acessorias.mapper import (
    AcessoriasMappingError,
    map_company_payload,
    map_delivery_company_block,
    map_delivery_payload,
)
from backend.app.services.integrations.acessorias.obligation_mapping import (
    MAPPED,
    map_external_department,
    map_obligation_name,
)
from backend.app.services.integrations.acessorias.regime import (
    MAPPED as REGIME_MAPPED,
    is_filial_regime_normal,
    normalize_identifier_root,
    upsert_regime_divergence_alert,
)
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


@dataclass(slots=True)
class AcessoriasSyncSummary:
    companies_received: int = 0
    companies_matched: int = 0
    companies_unmatched: int = 0
    company_snapshots_created: int = 0
    company_snapshots_updated: int = 0
    regimes_mapped: int = 0
    regimes_unmapped: int = 0
    deliveries_received: int = 0
    delivery_snapshots_created: int = 0
    delivery_snapshots_updated: int = 0
    statuses_created: int = 0
    statuses_updated: int = 0
    tasks_skipped: int = 0
    deliveries_filtered_out: int = 0
    unmapped_obligations: int = 0
    manual_review: int = 0
    failures: int = 0
    unknown_obligation_names: dict[str, int] = field(default_factory=dict)
    affected_companies_for_unmapped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "companies_received": self.companies_received,
            "companies_matched": self.companies_matched,
            "companies_unmatched": self.companies_unmatched,
            "company_snapshots_created": self.company_snapshots_created,
            "company_snapshots_updated": self.company_snapshots_updated,
            "regimes_mapped": self.regimes_mapped,
            "regimes_unmapped": self.regimes_unmapped,
            "deliveries_received": self.deliveries_received,
            "delivery_snapshots_created": self.delivery_snapshots_created,
            "delivery_snapshots_updated": self.delivery_snapshots_updated,
            "statuses_created": self.statuses_created,
            "statuses_updated": self.statuses_updated,
            "tasks_skipped": self.tasks_skipped,
            "deliveries_filtered_out": self.deliveries_filtered_out,
            "unmapped_obligations": self.unmapped_obligations,
            "manual_review": self.manual_review,
            "failures": self.failures,
            "unknown_obligation_names": self.unknown_obligation_names,
            "affected_companies_for_unmapped": sorted(set(self.affected_companies_for_unmapped)),
        }


@dataclass(slots=True)
class AcessoriasSyncResult:
    run: IntegrationSyncRun | None
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    dry_run: bool


@dataclass(slots=True)
class AcessoriasCompanySyncResult:
    payloads_found: int
    summary: dict[str, Any]
    errors: list[dict[str, Any]]
    dry_run: bool


class FixtureAcessoriasClient:
    def __init__(
        self,
        *,
        companies: list[dict[str, Any]],
        deliveries: list[dict[str, Any]] | None = None,
        deliveries_by_period: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._companies = companies
        self._deliveries = deliveries or []
        self._deliveries_by_period = deliveries_by_period or {}

    @classmethod
    def from_files(cls, *, companies_path: str | Path, deliveries_path: str | Path) -> "FixtureAcessoriasClient":
        return cls(
            companies=json.loads(Path(companies_path).read_text(encoding="utf-8")),
            deliveries=json.loads(Path(deliveries_path).read_text(encoding="utf-8")),
        )

    @classmethod
    def from_directory(cls, *, companies_path: str | Path, deliveries_dir: str | Path) -> "FixtureAcessoriasClient":
        deliveries_by_period: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(Path(deliveries_dir).glob("*.json")):
            deliveries_by_period[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            companies=json.loads(Path(companies_path).read_text(encoding="utf-8")),
            deliveries_by_period=deliveries_by_period,
        )

    def iter_companies(self) -> list[dict[str, Any]]:
        return list(self._companies)

    def iter_deliveries(self, identifier: str, *, dt_initial: date, dt_final: date) -> list[dict[str, Any]]:
        period_key = dt_initial.strftime("%Y-%m")
        del dt_final
        source = self._deliveries_by_period.get(period_key, self._deliveries)
        normalized_identifier = "".join(ch for ch in identifier if ch.isdigit())
        result: list[dict[str, Any]] = []
        for item in source:
            item_identifier = "".join(ch for ch in str(item.get("Identificador", "")) if ch.isdigit())
            if item_identifier == normalized_identifier:
                result.append(item)
        return result


def sync_acessorias_companies(
    session: Session,
    *,
    organization: Organization,
    client: AcessoriasClient | FixtureAcessoriasClient,
    dry_run: bool,
    summary: AcessoriasSyncSummary,
    errors: list[dict[str, Any]],
) -> None:
    payloads = list(client.iter_companies())
    _sync_acessorias_company_payloads(
        session,
        organization=organization,
        payloads=payloads,
        dry_run=dry_run,
        summary=summary,
        errors=errors,
    )


def sync_acessorias_company(
    session: Session,
    *,
    organization: Organization,
    identifier: str,
    client: AcessoriasClient | FixtureAcessoriasClient,
    dry_run: bool = False,
) -> AcessoriasCompanySyncResult:
    payload = client.get_company(identifier, registration_data=True)
    payloads = _coerce_company_payloads(payload)
    summary = AcessoriasSyncSummary()
    errors: list[dict[str, Any]] = []
    _sync_acessorias_company_payloads(
        session,
        organization=organization,
        payloads=payloads,
        dry_run=dry_run,
        summary=summary,
        errors=errors,
    )
    return AcessoriasCompanySyncResult(
        payloads_found=len(payloads),
        summary=summary.to_dict(),
        errors=errors,
        dry_run=dry_run,
    )


def _coerce_company_payloads(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    raise AcessoriasMappingError("Unexpected company payload format from Acessorias.")


def _sync_acessorias_company_payloads(
    session: Session,
    *,
    organization: Organization,
    payloads: list[dict[str, Any]],
    dry_run: bool,
    summary: AcessoriasSyncSummary,
    errors: list[dict[str, Any]],
) -> None:
    root_regime_map = _build_root_regime_map(payloads)

    for payload in payloads:
        summary.companies_received += 1
        try:
            mapped = map_company_payload(payload)
        except AcessoriasMappingError as exc:
            summary.failures += 1
            errors.append({"scope": "company", "error": str(exc)})
            continue

        mapped = _resolve_filial_regime_normal(
            session,
            organization_id=organization.id,
            mapped=mapped,
            root_regime_map=root_regime_map,
        )

        company = session.scalar(
            select(ExternalCompany).where(
                ExternalCompany.organization_id == organization.id,
                ExternalCompany.cnpj == mapped["identifier"],
            )
        )
        if company is None:
            summary.companies_unmatched += 1
        else:
            summary.companies_matched += 1

        if mapped["regime_mapping_status"] == REGIME_MAPPED:
            summary.regimes_mapped += 1
        else:
            summary.regimes_unmapped += 1

        if dry_run:
            continue

        snapshot = session.scalar(
            select(AcessoriasCompanySnapshot).where(
                AcessoriasCompanySnapshot.organization_id == organization.id,
                AcessoriasCompanySnapshot.external_company_id == mapped["external_company_id"],
            )
        )
        created = snapshot is None
        if snapshot is None:
            snapshot = AcessoriasCompanySnapshot(
                organization_id=organization.id,
                company_id=company.id if company is not None else None,
                **mapped,
            )
            session.add(snapshot)
        else:
            snapshot.company_id = company.id if company is not None else None
            for key, value in mapped.items():
                setattr(snapshot, key, value)
        session.flush()
        if created:
            summary.company_snapshots_created += 1
        else:
            summary.company_snapshots_updated += 1

        if company is not None:
            upsert_regime_divergence_alert(
                session,
                organization_id=organization.id,
                company_id=company.id,
                acessorias_snapshot=snapshot,
                econtrole_raw_payload=company.raw_econtrole,
            )


def _build_root_regime_map(payloads: list[dict[str, Any]]) -> dict[str, set[str]]:
    root_regime_map: dict[str, set[str]] = {}
    for payload in payloads:
        try:
            mapped = map_company_payload(payload)
        except AcessoriasMappingError:
            continue
        if mapped["regime_mapping_status"] != REGIME_MAPPED:
            continue
        root = normalize_identifier_root(mapped["identifier"])
        canonical = mapped["regime_canonical"]
        if root is None or canonical is None:
            continue
        root_regime_map.setdefault(root, set()).add(canonical)
    return root_regime_map


def _resolve_filial_regime_normal(
    session: Session,
    *,
    organization_id: int,
    mapped: dict[str, Any],
    root_regime_map: dict[str, set[str]],
) -> dict[str, Any]:
    if mapped["regime_mapping_status"] == REGIME_MAPPED:
        return mapped
    if not is_filial_regime_normal(mapped.get("regime_raw")):
        return mapped

    root = normalize_identifier_root(mapped.get("identifier"))
    if root is None:
        return mapped

    candidates = set(root_regime_map.get(root, set()))
    db_candidates = session.scalars(
        select(AcessoriasCompanySnapshot.regime_canonical).where(
            AcessoriasCompanySnapshot.organization_id == organization_id,
            AcessoriasCompanySnapshot.identifier.like(f"{root}%"),
            AcessoriasCompanySnapshot.regime_mapping_status == REGIME_MAPPED,
            AcessoriasCompanySnapshot.regime_canonical.is_not(None),
        )
    ).all()
    candidates.update(candidate for candidate in db_candidates if candidate is not None)

    if len(candidates) != 1:
        return mapped

    canonical = next(iter(candidates))
    adjusted = dict(mapped)
    adjusted["regime_canonical"] = canonical
    adjusted["regime_mapping_status"] = REGIME_MAPPED
    return adjusted


def sync_acessorias_deliveries(
    session: Session,
    *,
    organization: Organization,
    client: AcessoriasClient | FixtureAcessoriasClient,
    period: FiscalPeriod,
    company_id: int | None,
    only_active: bool,
    fiscal_only: bool,
    dry_run: bool,
    summary: AcessoriasSyncSummary,
    errors: list[dict[str, Any]],
) -> None:
    obligations = session.scalars(select(FiscalObligation).where(FiscalObligation.active.is_(True))).all()
    company_query = select(ExternalCompany).where(ExternalCompany.organization_id == organization.id)
    if only_active:
        company_query = company_query.where(ExternalCompany.active.is_(True))
    if company_id is not None:
        company_query = company_query.where(ExternalCompany.id == company_id)
    companies = session.scalars(company_query.order_by(ExternalCompany.id.asc())).all()

    dt_initial = date(period.year, period.month, 1)
    dt_final = date(period.year, period.month, calendar.monthrange(period.year, period.month)[1])

    for company in companies:
        try:
            blocks = list(client.iter_deliveries(company.cnpj, dt_initial=dt_initial, dt_final=dt_final))
        except Exception as exc:
            summary.failures += 1
            errors.append({"scope": "delivery_company", "company_id": company.id, "error": str(exc)})
            continue

        for block_payload in blocks:
            try:
                block = map_delivery_company_block(block_payload)
            except AcessoriasMappingError as exc:
                summary.failures += 1
                errors.append({"scope": "delivery_block", "company_id": company.id, "error": str(exc)})
                continue

            company_snapshot = session.scalar(
                select(AcessoriasCompanySnapshot).where(
                    AcessoriasCompanySnapshot.organization_id == organization.id,
                    AcessoriasCompanySnapshot.external_company_id == block.external_company_id,
                )
            )
            for item in block_payload.get("Entregas", []):
                summary.deliveries_received += 1
                try:
                    mapped = map_delivery_payload(block, item)
                except AcessoriasMappingError as exc:
                    summary.failures += 1
                    errors.append({"scope": "delivery", "company_id": company.id, "error": str(exc)})
                    continue

                obligation_match = map_obligation_name(mapped["obligation_name"], obligations)
                mapped["obligation_id"] = obligation_match.obligation_id
                mapped["obligation_mapping_status"] = obligation_match.mapping_status
                if mapped["normalized_status"] == ReconciliationStatus.CONFERENCIA_MANUAL.value:
                    summary.manual_review += 1
                if obligation_match.mapping_status != MAPPED:
                    summary.unmapped_obligations += 1
                    summary.unknown_obligation_names[mapped["obligation_name"]] = (
                        summary.unknown_obligation_names.get(mapped["obligation_name"], 0) + 1
                    )
                    summary.affected_companies_for_unmapped.append(company.razao_social)

                if mapped["external_type"] == "T":
                    summary.tasks_skipped += 1

                if fiscal_only and not _is_fiscal_relevant_delivery(mapped=mapped, obligation_mapping_status=obligation_match.mapping_status):
                    summary.deliveries_filtered_out += 1
                    continue

                if dry_run:
                    continue

                snapshot = session.scalar(
                    select(AcessoriasDeliverySnapshot).where(
                        AcessoriasDeliverySnapshot.organization_id == organization.id,
                        AcessoriasDeliverySnapshot.external_company_id == mapped["external_company_id"],
                        AcessoriasDeliverySnapshot.external_delivery_id == mapped["external_delivery_id"],
                    )
                )
                created = snapshot is None
                if snapshot is None:
                    snapshot = AcessoriasDeliverySnapshot(
                        organization_id=organization.id,
                        company_id=company.id,
                        period_id=period.id,
                        company_snapshot_id=company_snapshot.id if company_snapshot is not None else None,
                        **mapped,
                    )
                    session.add(snapshot)
                else:
                    snapshot.company_id = company.id
                    snapshot.period_id = period.id
                    snapshot.company_snapshot_id = company_snapshot.id if company_snapshot is not None else None
                    for key, value in mapped.items():
                        setattr(snapshot, key, value)
                session.flush()
                if created:
                    summary.delivery_snapshots_created += 1
                else:
                    summary.delivery_snapshots_updated += 1

                if mapped["external_type"] != "O" or obligation_match.mapping_status != MAPPED:
                    continue
                _upsert_fiscal_status(
                    session,
                    organization_id=organization.id,
                    company=company,
                    period=period,
                    obligation=next(ob for ob in obligations if ob.id == obligation_match.obligation_id),
                    snapshot=snapshot,
                    summary=summary,
                )


def sync_acessorias_period(
    session: Session,
    *,
    period: str,
    org_slug: str | None = None,
    organization: Organization | None = None,
    company_id: int | None = None,
    dry_run: bool = False,
    sync_companies: bool = True,
    sync_deliveries: bool = True,
    only_active: bool = True,
    fiscal_only: bool = False,
    run_metadata_extra: dict[str, Any] | None = None,
    client: AcessoriasClient | FixtureAcessoriasClient | None = None,
) -> AcessoriasSyncResult:
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
    period_row = session.scalar(
        select(FiscalPeriod).where(
            FiscalPeriod.organization_id == organization.id,
            FiscalPeriod.competencia == period,
        )
    )
    if period_row is None:
        raise ValueError(f"FiscalPeriod '{period}' was not found for organization '{organization.slug}'.")

    summary = AcessoriasSyncSummary()
    errors: list[dict[str, Any]] = []
    run: IntegrationSyncRun | None = None
    run_metadata = {
        "organization_slug": organization.slug,
        "period": period,
        "company_id": company_id,
        "sync_companies": sync_companies,
        "sync_deliveries": sync_deliveries,
        "only_active": only_active,
        "fiscal_only": fiscal_only,
    }
    if run_metadata_extra:
        run_metadata.update(run_metadata_extra)
    if not dry_run:
        run = IntegrationSyncRun(
            organization_id=organization.id,
            integration_account_id=None,
            provider="ACESSORIAS",
            job_name="sync_acessorias_period",
            status="RUNNING",
            started_at=datetime.now(timezone.utc),
            summary={},
            run_metadata=run_metadata,
        )
        session.add(run)
        session.commit()

    try:
        if client is None:
            from backend.app.core.config import get_settings

            client = AcessoriasClient.from_settings(get_settings())

        if sync_companies:
            sync_acessorias_companies(
                session,
                organization=organization,
                client=client,
                dry_run=dry_run,
                summary=summary,
                errors=errors,
            )
        if sync_deliveries:
            sync_acessorias_deliveries(
                session,
                organization=organization,
                client=client,
                period=period_row,
                company_id=company_id,
                only_active=only_active,
                fiscal_only=fiscal_only,
                dry_run=dry_run,
                summary=summary,
                errors=errors,
            )

        result_summary = summary.to_dict()
        if not dry_run and run is not None:
            run.finished_at = datetime.now(timezone.utc)
            run.processed_count = summary.companies_received + summary.deliveries_received
            run.created_count = (
                summary.company_snapshots_created + summary.delivery_snapshots_created + summary.statuses_created
            )
            run.updated_count = (
                summary.company_snapshots_updated + summary.delivery_snapshots_updated + summary.statuses_updated
            )
            run.error_count = summary.failures
            run.errors = errors or None
            run.summary = result_summary
            run.status = _resolve_run_status(summary=summary)
            session.commit()
        return AcessoriasSyncResult(run=run, summary=result_summary, errors=errors, dry_run=dry_run)
    except Exception as exc:
        if not dry_run and run is not None:
            session.rollback()
            failed_run = session.get(IntegrationSyncRun, run.id)
            if failed_run is not None:
                failed_run.finished_at = datetime.now(timezone.utc)
                failed_run.status = "FAILED"
                failed_run.error_count = max(failed_run.error_count, 1)
                failed_run.errors = (errors or []) + [{"scope": "global", "error": str(exc)}]
                failed_run.summary = summary.to_dict()
                session.commit()
        raise


def _resolve_run_status(*, summary: AcessoriasSyncSummary) -> str:
    processed = summary.companies_received + summary.deliveries_received
    if processed == 0:
        return "FAILED"
    if summary.failures > 0:
        return "PARTIAL"
    return "SUCCESS"


def _is_fiscal_relevant_delivery(*, mapped: dict[str, Any], obligation_mapping_status: str) -> bool:
    if mapped.get("external_type") != "O":
        return False
    if obligation_mapping_status == MAPPED:
        return True
    department_name = mapped.get("department_name")
    return map_external_department(department_name, "COMPARTILHADO") == "FISCAL"


def _upsert_fiscal_status(
    session: Session,
    *,
    organization_id: int,
    company: ExternalCompany,
    period: FiscalPeriod,
    obligation: FiscalObligation,
    snapshot: AcessoriasDeliverySnapshot,
    summary: AcessoriasSyncSummary,
) -> None:
    row = session.scalar(
        select(FiscalObligationStatus).where(
            FiscalObligationStatus.company_id == company.id,
            FiscalObligationStatus.period_id == period.id,
            FiscalObligationStatus.obligation_id == obligation.id,
        )
    )
    delivered_at = snapshot.finalized_at
    if delivered_at is None and snapshot.delivered_date is not None:
        delivered_at = datetime.combine(snapshot.delivered_date, time.min, tzinfo=timezone.utc)
    confidence = 70.0 if snapshot.normalized_status == ReconciliationStatus.CONFERENCIA_MANUAL.value else 100.0
    responsible_department = map_external_department(snapshot.department_name, obligation.department_default)
    notes = snapshot.external_status or None

    created = row is None
    if row is None:
        row = FiscalObligationStatus(
            organization_id=organization_id,
            company_id=company.id,
            period_id=period.id,
            obligation_id=obligation.id,
            status=snapshot.normalized_status,
            responsible_department=responsible_department,
            origin_reason="ACESSORIAS_DELIVERY",
            confidence=confidence,
            main_evidence_id=None,
            last_source="ACESSORIAS_API",
            due_date=snapshot.due_date,
            delivered_at=delivered_at,
            notes=notes,
        )
        session.add(row)
    else:
        row.status = snapshot.normalized_status
        row.responsible_department = responsible_department
        row.origin_reason = "ACESSORIAS_DELIVERY"
        row.confidence = confidence
        row.last_source = "ACESSORIAS_API"
        row.due_date = snapshot.due_date
        row.delivered_at = delivered_at
        row.notes = notes
    session.flush()
    if created:
        summary.statuses_created += 1
    else:
        summary.statuses_updated += 1


def audit_manual_sync(
    session: Session,
    *,
    organization_id: int,
    actor_id: str,
    period: str,
    company_id: int | None,
    dry_run: bool,
    summary: dict[str, Any],
) -> None:
    record_audit_event(
        session,
        event_type="acessorias_sync_manual",
        message="Acessorias sync executed manually.",
        actor_type="user",
        actor_id=actor_id,
        resource_type="organization",
        resource_id=str(organization_id),
        event_metadata={
            "period": period,
            "company_id": company_id,
            "dry_run": dry_run,
            "summary": summary,
        },
    )
    session.commit()
