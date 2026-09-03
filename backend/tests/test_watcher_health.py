from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.api.v1.endpoints import lumen as lumen_endpoint
from backend.app.core.config import Settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.organization import Organization
from backend.app.models.watcher_agent_health import WatcherAgentHealth
from backend.app.schemas.watcher import WatcherHeartbeatRequest
from backend.app.services.watcher_health import get_watcher_health, record_heartbeat
from backend.app.services.auth import ROLE_ADMIN, ROLE_DEV, ROLE_VIEW
from backend.tests.test_lumen_read_endpoints import login_headers, seed_auth_context


def _payload(**overrides: object) -> WatcherHeartbeatRequest:
    value: dict[str, object] = {
        "status": "RUNNING", "started_at": "2026-09-02T10:00:00+00:00", "last_scan_at": "2026-09-02T10:01:00+00:00",
        "last_successful_send_at": None, "last_error_code": None,
        "counters": {"candidates_seen": 1, "pending_stability": 0, "pending_retry": 0, "sent_success": 0, "rejected": 0},
    }
    value.update(overrides)
    return WatcherHeartbeatRequest.model_validate(value)


def test_heartbeat_is_tenant_scoped_and_derives_stale(db_session) -> None:
    org = Organization(name="Watcher health", slug="watcher-health")
    db_session.add(org)
    db_session.flush()
    assert get_watcher_health(db_session, organization_id=org.id, stale_seconds=60).status == "NEVER_SEEN"
    row = record_heartbeat(db_session, organization=org, payload=_payload())
    assert get_watcher_health(db_session, organization_id=org.id, stale_seconds=60).status == "RUNNING"
    row.received_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    assert get_watcher_health(db_session, organization_id=org.id, stale_seconds=60).status == "STALE"


def test_heartbeat_contract_rejects_sensitive_or_extra_fields() -> None:
    for key in ("token", "authorization", "organization_id", "relative_path", "raw_text"):
        try:
            _payload(**{key: "forbidden"})
        except ValueError:
            continue
        raise AssertionError(f"{key} must be rejected")


def test_heartbeat_upserts_and_preserves_reported_lifecycle_states(db_session) -> None:
    org = Organization(name="Heartbeat upsert", slug="heartbeat-upsert")
    db_session.add(org)
    db_session.flush()
    record_heartbeat(db_session, organization=org, payload=_payload(status="RUNNING"))
    record_heartbeat(db_session, organization=org, payload=_payload(status="DEGRADED", last_error_code="NETWORK_ERROR"))
    assert db_session.scalar(select(func.count()).select_from(WatcherAgentHealth)) == 1
    assert get_watcher_health(db_session, organization_id=org.id, stale_seconds=60).status == "DEGRADED"
    record_heartbeat(db_session, organization=org, payload=_payload(status="STOPPED"))
    assert get_watcher_health(db_session, organization_id=org.id, stale_seconds=60).status == "STOPPED"


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    original_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db_session.commit = original_commit  # type: ignore[method-assign]


def test_heartbeat_endpoint_derives_organization_and_human_read_is_tenant_scoped(client, db_session, monkeypatch) -> None:
    _, agent_org, _ = seed_auth_context(db_session, role=ROLE_ADMIN, slug="heartbeat-agent")
    viewer, other_org, viewer_password = seed_auth_context(db_session, role=ROLE_VIEW, slug="heartbeat-viewer")
    monkeypatch.setattr(lumen_endpoint, "get_settings", lambda: Settings(lumen_watcher_agent_token="synthetic", lumen_watcher_agent_org_slug=agent_org.slug))
    body = _payload().model_dump(mode="json")
    assert client.post("/api/v1/lumen/evidences/watcher-heartbeat", json=body, headers={"X-Lumen-Agent-Token": "synthetic"}).status_code == 204
    assert client.post("/api/v1/lumen/evidences/watcher-heartbeat", json={**body, "relative_path": "forbidden"}, headers={"X-Lumen-Agent-Token": "synthetic"}).status_code == 422
    response = client.get("/api/v1/lumen/integrations/watcher-health", headers=login_headers(client, email=viewer.email, password=viewer_password))
    assert response.status_code == 200 and response.json()["status"] == "NEVER_SEEN"
    assert other_org.id != agent_org.id


@pytest.mark.parametrize("role, expected", [(ROLE_VIEW, 403), (ROLE_ADMIN, 200), (ROLE_DEV, 200)])
def test_reprocess_endpoint_requires_admin_or_dev(client, db_session, role: str, expected: int) -> None:
    user, _, password = seed_auth_context(db_session, role=role, slug=f"reprocess-{role.lower()}")
    response = client.post("/api/v1/lumen/evidences/watcher-events/reprocess", headers=login_headers(client, email=user.email, password=password))
    assert response.status_code == expected
