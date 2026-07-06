from backend.app.models.audit_log import AuditLog
from backend.app.services.audit import record_audit_event


def test_record_audit_event_persists_row(db_session) -> None:
    audit_log = record_audit_event(
        db_session,
        event_type="health.checked",
        message="Health endpoint called",
        actor_type="system",
        actor_id="test-suite",
        resource_type="endpoint",
        resource_id="/healthz",
        event_metadata={"stage": "S2"},
        raw_payload={"status": "ok"},
    )
    db_session.commit()

    saved = db_session.get(AuditLog, audit_log.id)

    assert saved is not None
    assert saved.event_type == "health.checked"
    assert saved.message == "Health endpoint called"
    assert saved.event_metadata == {"stage": "S2"}
    assert saved.raw_payload == {"status": "ok"}
    assert saved.created_at is not None
