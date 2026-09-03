"""Explicit, bounded retry of watcher events that could not yet be resolved."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.organization import Organization
from backend.app.models.watcher_file_event import WatcherFileEvent
from backend.app.schemas.watcher import WatcherEventIngestRequest
from backend.app.services.audit import record_audit_event
from backend.app.services.watcher_ingest import resolve_company, resolve_period


@dataclass(frozen=True, slots=True)
class WatcherReprocessResult:
    inspected: int
    evidence_created: int
    unresolved: int


def reprocess_unresolved_watcher_events(session: Session, *, organization: Organization, limit: int = 100) -> WatcherReprocessResult:
    events = session.scalars(
        select(WatcherFileEvent)
        .where(WatcherFileEvent.organization_id == organization.id)
        .where(~WatcherFileEvent.id.in_(select(FiscalEvidence.watcher_event_id).where(FiscalEvidence.watcher_event_id.is_not(None))))
        .order_by(WatcherFileEvent.id)
        .limit(limit)
    ).all()
    created = unresolved = 0
    for event in events:
        raw = event.raw_payload or {}
        try:
            payload = WatcherEventIngestRequest.model_validate({key: value for key, value in raw.items() if not key.startswith("_")})
        except ValueError:
            unresolved += 1
            continue
        company, company_resolution = resolve_company(session, organization_id=organization.id, folder_company=payload.folder_company)
        period, period_resolution = resolve_period(session, organization_id=organization.id, folder_period=payload.folder_period)
        raw["_lumen_resolution"] = {"company": company_resolution.value, "period": period_resolution.value}
        event.raw_payload = raw
        event.company_id = company.id if company else None
        event.period_id = period.id if period else None
        if company is None or period is None:
            unresolved += 1
            continue
        evidence = FiscalEvidence(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            watcher_event_id=event.id,
            source="WATCHER_FILE",
            source_type="WATCHER_INGEST",
            file_path=event.normalized_relative_path,
            file_hash=event.file_hash,
            file_name=event.file_name,
            raw_payload={"schema_version": payload.schema_version, "pdf_probe": payload.pdf_probe.model_dump(), "watcher_event_id": event.id},
            status="PENDENTE",
        )
        session.add(evidence)
        created += 1
        record_audit_event(session, event_type="watcher.event.reprocessed", message="Watcher event reprocessed.", actor_type="USER", resource_type="watcher_file_event", resource_id=str(event.id), event_metadata={"watcher_event_id": event.id, "evidence_created": True})
    session.flush()
    return WatcherReprocessResult(inspected=len(events), evidence_created=created, unresolved=unresolved)
