"""Explicit, bounded retry of watcher events that could not yet be resolved."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.organization import Organization
from backend.app.models.watcher_file_event import WatcherFileEvent
from backend.app.schemas.watcher import WatcherEventIngestRequest
from backend.app.services.audit import record_audit_event
from backend.app.services.watcher_ingest import (
    WatcherIngestError,
    link_watcher_event_to_document_evidence,
    resolve_company,
    resolve_period,
)


@dataclass(frozen=True, slots=True)
class WatcherReprocessResult:
    inspected: int
    evidence_created: int
    unresolved: int


def reprocess_unresolved_watcher_events(session: Session, *, organization: Organization, limit: int = 100) -> WatcherReprocessResult:
    events = session.scalars(
        select(WatcherFileEvent)
        .where(WatcherFileEvent.organization_id == organization.id)
        .where(WatcherFileEvent.evidence_id.is_(None))
        .order_by(WatcherFileEvent.id)
        .limit(limit)
    ).all()
    created = unresolved = 0
    for event in events:
        raw = event.raw_payload or {}
        try:
            payload = WatcherEventIngestRequest.model_validate({key: value for key, value in raw.items() if not key.startswith("_")})
        except ValueError:
            payload = None
        if payload is not None:
            company, company_resolution = resolve_company(
                session,
                organization_id=organization.id,
                folder_company=payload.folder_company,
            )
            period, period_resolution = resolve_period(
                session,
                organization_id=organization.id,
                folder_period=payload.folder_period,
            )
            raw["_lumen_resolution"] = {
                "company": company_resolution.value,
                "period": period_resolution.value,
            }
            event.raw_payload = raw
            event.company_id = company.id if company else None
            event.period_id = period.id if period else None
        if not event.file_hash:
            unresolved += 1
            continue
        provenance = _reprocess_provenance(raw, payload)
        try:
            evidence, evidence_created = link_watcher_event_to_document_evidence(
                session,
                event=event,
                company_id=event.company_id,
                period_id=event.period_id,
                provenance=provenance,
            )
        except WatcherIngestError:
            unresolved += 1
            continue
        created += int(evidence_created)
        record_audit_event(
            session,
            event_type="watcher.event.reprocessed",
            message="Watcher event reprocessed.",
            actor_type="USER",
            resource_type="watcher_file_event",
            resource_id=str(event.id),
            event_metadata={
                "watcher_event_id": event.id,
                "evidence_id": evidence.id,
                "evidence_created": evidence_created,
                "evidence_reused": not evidence_created,
            },
        )
    session.flush()
    return WatcherReprocessResult(inspected=len(events), evidence_created=created, unresolved=unresolved)


def _reprocess_provenance(
    raw: dict[str, object],
    payload: WatcherEventIngestRequest | None,
) -> dict[str, object]:
    if payload is not None:
        return {
            "schema_version": payload.schema_version,
            "pdf_probe": payload.pdf_probe.model_dump(),
        }
    provenance: dict[str, object] = {}
    for key in ("contract_version", "technical_probe", "path_context"):
        if key in raw:
            provenance[key] = raw[key]
    return provenance
