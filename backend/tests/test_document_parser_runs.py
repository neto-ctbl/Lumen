from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.fiscal_document_parser_run import FiscalDocumentParserRun
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherParserRunRequest
from backend.app.services.document_parser_runs import ParserRunEvidenceNotFound, register_document_parser_run
from backend.tests.test_watcher_ingest import _configure_agent


def _seed_org(db_session, slug: str) -> Organization:
    organization = Organization(name=f"Synthetic {slug}", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _seed_evidence(db_session, organization: Organization, *, source: str = "WATCHER_FILE") -> FiscalEvidence:
    evidence = FiscalEvidence(
        organization_id=organization.id,
        source=source,
        source_type="WATCHER_INGEST" if source == "WATCHER_FILE" else "SYNTHETIC_TEST",
        file_hash=f"{organization.id:064x}"[-64:],
        status="PENDENTE",
    )
    db_session.add(evidence)
    db_session.flush()
    return evidence


def _payload(*, version: str = "1.0.0") -> WatcherParserRunRequest:
    return WatcherParserRunRequest.model_validate(
        {
            "parser_name": "synthetic.document",
            "parser_version": version,
            "document_family": "SYNTHETIC_DOCUMENT",
            "extraction_status": "MATCHED",
            "confidence": 0.95,
            "signals": [
                {
                    "name": "period_from_content",
                    "value": "2026-08",
                    "provenance": "CONTENT",
                    "confidence": 0.95,
                }
            ],
            "warnings": ["SYNTHETIC_ONLY"],
            "structured_data": {"synthetic_marker": True},
        }
    )


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


def test_parser_run_create_replay_and_new_version_preserve_history(db_session) -> None:
    organization = _seed_org(db_session, "parser-run-history")
    evidence = _seed_evidence(db_session, organization)
    before_obligations = db_session.scalar(select(func.count()).select_from(FiscalObligationStatus))

    first = register_document_parser_run(
        db_session, organization=organization, evidence_id=evidence.id, payload=_payload()
    )
    replay = register_document_parser_run(
        db_session, organization=organization, evidence_id=evidence.id, payload=_payload()
    )
    upgraded = register_document_parser_run(
        db_session, organization=organization, evidence_id=evidence.id, payload=_payload(version="2.0.0")
    )

    assert first.created and not replay.created and upgraded.created
    assert first.parser_run.id == replay.parser_run.id
    assert first.parser_run.id != upgraded.parser_run.id
    assert first.parser_run.structured_payload["signals"][0]["provenance"] == "CONTENT"
    assert db_session.scalar(select(func.count()).select_from(FiscalDocumentParserRun)) == 2
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == before_obligations
    db_session.refresh(evidence)
    assert evidence.detected_tax is None
    assert evidence.detected_obligation is None
    assert evidence.cnpj_detected is None
    assert evidence.competencia_detected is None
    assert evidence.confidence is None


def test_missing_cross_tenant_and_non_watcher_evidences_are_indistinguishable(db_session) -> None:
    organization_a = _seed_org(db_session, "parser-run-org-a")
    organization_b = _seed_org(db_session, "parser-run-org-b")
    evidence_b = _seed_evidence(db_session, organization_b)
    non_watcher = _seed_evidence(db_session, organization_a, source="DOMINIO_FOLHA_PDF")

    for evidence_id in (999_999_999, evidence_b.id, non_watcher.id):
        with pytest.raises(ParserRunEvidenceNotFound):
            register_document_parser_run(
                db_session,
                organization=organization_a,
                evidence_id=evidence_id,
                payload=_payload(),
            )

    assert db_session.scalar(
        select(func.count()).select_from(FiscalDocumentParserRun).where(
            FiscalDocumentParserRun.organization_id == organization_a.id
        )
    ) == 0


def test_m2m_endpoint_derives_tenant_and_is_idempotent(client, db_session, monkeypatch) -> None:
    organization = _seed_org(db_session, "parser-run-endpoint")
    evidence = _seed_evidence(db_session, organization)
    headers = _configure_agent(monkeypatch, organization)
    endpoint = f"/api/v1/lumen/evidences/{evidence.id}/parser-runs"
    payload = _payload().model_dump(mode="json")

    assert client.post(endpoint, json=payload).status_code == 401
    first = client.post(endpoint, json=payload, headers=headers)
    replay = client.post(endpoint, json=payload, headers=headers)

    assert first.status_code == 200 and replay.status_code == 200
    assert first.json()["parser_run_created"] is True
    assert replay.json()["parser_run_created"] is False
    assert first.json()["parser_run_id"] == replay.json()["parser_run_id"]

    payload["organization_id"] = organization.id
    assert client.post(endpoint, json=payload, headers=headers).status_code == 422


def test_m2m_endpoint_returns_same_404_for_missing_and_cross_tenant(client, db_session, monkeypatch) -> None:
    organization_a = _seed_org(db_session, "parser-run-endpoint-a")
    organization_b = _seed_org(db_session, "parser-run-endpoint-b")
    evidence_b = _seed_evidence(db_session, organization_b)
    headers = _configure_agent(monkeypatch, organization_a)
    payload = _payload().model_dump(mode="json")

    missing = client.post("/api/v1/lumen/evidences/999999999/parser-runs", json=payload, headers=headers)
    cross_tenant = client.post(
        f"/api/v1/lumen/evidences/{evidence_b.id}/parser-runs",
        json=payload,
        headers=headers,
    )

    assert missing.status_code == cross_tenant.status_code == 404
    assert missing.json() == cross_tenant.json() == {"detail": "Watcher evidence not found."}


@pytest.mark.parametrize("forbidden_name", ["raw_text", "raw_payload", "token", "file_bytes"])
def test_contract_rejects_raw_content_and_secret_fields(forbidden_name: str) -> None:
    raw_payload = _payload().model_dump(mode="json")
    raw_payload["structured_data"] = {forbidden_name: "synthetic value"}

    with pytest.raises(ValueError, match="forbidden raw-content or secret"):
        WatcherParserRunRequest.model_validate(raw_payload)
