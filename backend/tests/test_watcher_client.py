from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.watcher.client import ClientResponse, WatcherApiClient, _category
from agent.watcher.config import WatcherConfig
from backend.app.db.session import get_db
from backend.app.main import app
from backend.tests.test_watcher_ingest import _configure_agent, _payload as _ingest_payload, _seed_company_period, _seed_org


def _config(tmp_path: Path) -> WatcherConfig:
    return WatcherConfig(root=tmp_path, agent_token="synthetic-agent-token")


def _payload() -> dict[str, object]:
    return {"schema_version": "1", "event_type": "FILE_STABLE", "classifier_hint": "UNKNOWN"}


@pytest.fixture()
def endpoint_client(db_session) -> Generator[TestClient, None, None]:
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


def test_client_sends_only_m2m_header_and_metadata(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def transport(url: str, body: bytes, headers: dict[str, str], timeout: float) -> ClientResponse:
        captured.update(url=url, body=json.loads(body), headers=headers, timeout=timeout)
        return ClientResponse(200, "SUCCESS", {"event_id": 1})

    result = WatcherApiClient(_config(tmp_path), transport=transport).send(_payload())

    assert result.category == "SUCCESS"
    assert captured["url"] == "http://localhost:8000/api/v1/lumen/evidences/watcher-event"
    assert captured["headers"] == {"Content-Type": "application/json", "X-Lumen-Agent-Token": "synthetic-agent-token"}
    assert "organization_id" not in captured["body"]
    assert "Authorization" not in captured["headers"]


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (ClientResponse(200, "SUCCESS"), "SUCCESS"),
        (ClientResponse(422, "REJECTED"), "REJECTED"),
        (ClientResponse(401, "AUTH_ERROR"), "AUTH_ERROR"),
        (ClientResponse(503, "UNAVAILABLE"), "UNAVAILABLE"),
        (ClientResponse(500, "SERVER_ERROR"), "SERVER_ERROR"),
        (ClientResponse(None, "NETWORK_ERROR"), "NETWORK_ERROR"),
    ],
)
def test_client_preserves_sanitized_transport_categories(tmp_path: Path, response: ClientResponse, expected: str) -> None:
    result = WatcherApiClient(_config(tmp_path), transport=lambda *_: response).send(_payload())
    assert result.category == expected


def test_client_does_not_attempt_requests_without_a_token(tmp_path: Path) -> None:
    called = False

    def transport(*_args: object) -> ClientResponse:
        nonlocal called
        called = True
        return ClientResponse(200, "SUCCESS")

    result = WatcherApiClient(WatcherConfig(root=tmp_path), transport=transport).send(_payload())
    assert result.category == "AUTH_CONFIGURATION"
    assert not called


def test_remote_insecure_http_is_rejected_by_config() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        WatcherConfig.from_env({"LUMEN_WATCHER_API_BASE_URL": "http://example.test"})


def test_agent_client_payload_is_accepted_by_watcher_endpoint(endpoint_client, db_session, monkeypatch, tmp_path: Path) -> None:
    organization = _seed_org(db_session)
    _seed_company_period(db_session, organization)
    headers = _configure_agent(monkeypatch, organization)

    def endpoint_transport(_url: str, body: bytes, request_headers: dict[str, str], _timeout: float) -> ClientResponse:
        response = endpoint_client.post("/api/v1/lumen/evidences/watcher-event", content=body, headers=request_headers)
        return ClientResponse(response.status_code, _category(response.status_code), response.json())

    result = WatcherApiClient(_config(tmp_path), transport=endpoint_transport).send(_ingest_payload(classifier_hint="UNKNOWN"))

    assert result.category == "SUCCESS"
    assert result.body is not None and result.body["event_created"] is True
    assert headers["X-Lumen-Agent-Token"] == "synthetic-agent-token"
