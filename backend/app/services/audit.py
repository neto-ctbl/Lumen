from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.audit_log import AuditLog


def record_audit_event(
    session: Session,
    *,
    event_type: str,
    message: str,
    actor_type: str | None = None,
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    event_metadata: dict[str, Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        event_type=event_type,
        message=message,
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=event_metadata,
        raw_payload=raw_payload,
    )
    session.add(audit_log)
    session.flush()
    return audit_log
