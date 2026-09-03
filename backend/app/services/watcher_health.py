"""Persistence and derived human-readable state for watcher heartbeats."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.organization import Organization
from backend.app.models.watcher_agent_health import WatcherAgentHealth
from backend.app.schemas.watcher import WatcherHeartbeatRequest, WatcherHealthResponse


def record_heartbeat(session: Session, *, organization: Organization, payload: WatcherHeartbeatRequest) -> WatcherAgentHealth:
    row = session.scalar(select(WatcherAgentHealth).where(WatcherAgentHealth.organization_id == organization.id))
    if row is None:
        row = WatcherAgentHealth(organization_id=organization.id, reported_status=payload.status, counters={})
        session.add(row)
    row.reported_status = payload.status
    row.last_error_code = payload.last_error_code
    row.agent_started_at = payload.started_at
    row.agent_last_scan_at = payload.last_scan_at
    row.agent_last_successful_send_at = payload.last_successful_send_at
    row.counters = payload.counters.model_dump()
    row.received_at = datetime.now(timezone.utc)
    session.flush()
    return row


def get_watcher_health(session: Session, *, organization_id: int, stale_seconds: int, now: datetime | None = None) -> WatcherHealthResponse:
    row = session.scalar(select(WatcherAgentHealth).where(WatcherAgentHealth.organization_id == organization_id))
    if row is None:
        return WatcherHealthResponse(status="NEVER_SEEN", reported_status=None, received_at=None, last_error_code=None, counters={})
    now = now or datetime.now(timezone.utc)
    received_at = _aware(row.received_at)
    status = "STALE" if received_at < now - timedelta(seconds=stale_seconds) else row.reported_status
    return WatcherHealthResponse(
        status=status,
        reported_status=row.reported_status,
        received_at=received_at,
        last_error_code=row.last_error_code,
        started_at=row.agent_started_at,
        last_scan_at=row.agent_last_scan_at,
        last_successful_send_at=row.agent_last_successful_send_at,
        counters=row.counters or {},
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
