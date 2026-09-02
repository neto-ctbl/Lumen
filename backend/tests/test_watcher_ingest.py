from __future__ import annotations

from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from backend.app.api.v1.endpoints import lumen as lumen_endpoint
from backend.app.core.config import Settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.audit_log import AuditLog
from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.watcher_file_event import WatcherFileEvent
from backend.app.schemas.watcher import WatcherEventIngestRequest
from backend.app.services import lumen_read_model
from backend.app.services.watcher_ingest import (
    CompanyResolution,
    PeriodResolution,
    WatcherIngestError,
    ingest_watcher_event,
    resolve_company,
    validate_watcher_event_semantics,
)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1",
        "event_type": "FILE_STABLE",
        "relative_path": r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\DAS 07-2026.pdf",
        "file_name": "DAS 07-2026.pdf",
        "file_sha256": "a" * 64,
        "file_size": 12345,
        "detected_at": "2026-08-31T15:00:00+00:00",
        "folder_period": "2026-07",
        "folder_company": "EMPRESA EXEMPLO",
        "classifier_hint": "DAS",
        "pdf_probe": {"is_pdf": True, "page_count": 1, "has_extractable_text": True, "text_length": 300},
    }
    payload.update(overrides)
    return payload


def _seed_org(db_session, slug: str = "watcher-org") -> Organization:
    organization = Organization(name=f"Organization {slug}", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _seed_company_period(db_session, organization: Organization, *, alias: str = "EMPRESA EXEMPLO") -> tuple[ExternalCompany, FiscalPeriod]:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=f"{organization.id:014d}",
        razao_social="RAZAO SOCIAL EXEMPLO",
        nome_fantasia="FANTASIA EXEMPLO",
        apelido_pasta=alias,
        active=True,
    )
    period = FiscalPeriod(organization_id=organization.id, year=2026, month=7, competencia="2026-07", status="OPEN")
    db_session.add_all([company, period])
    db_session.flush()
    return company, period


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


def _configure_agent(monkeypatch, organization: Organization, token: str = "synthetic-agent-token") -> dict[str, str]:
    monkeypatch.setattr(
        lumen_endpoint,
        "get_settings",
        lambda: Settings(lumen_watcher_agent_token=token, lumen_watcher_agent_org_slug=organization.slug),
    )
    return {"X-Lumen-Agent-Token": token}


def test_semantic_validation_rejects_paths_and_client_owned_ids() -> None:
    valid = WatcherEventIngestRequest.model_validate(_payload())
    assert validate_watcher_event_semantics(valid).normalized_relative_path.startswith("empresa exemplo")
    for field, value in [
        ("relative_path", r"G:\EMPRESAS\x.pdf"),
        ("relative_path", r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\..\DAS.pdf"),
        ("file_name", "other.pdf"),
        ("folder_company", "OTHER"),
        ("folder_period", "2026-08"),
        ("relative_path", r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\DAS.xml"),
    ]:
        data = _payload(**{field: value})
        if field == "relative_path" and str(value).endswith(".xml"):
            data["file_name"] = "DAS.xml"
        with pytest.raises(WatcherIngestError):
            validate_watcher_event_semantics(WatcherEventIngestRequest.model_validate(data))
    for forbidden in ("organization_id", "company_id", "period_id", "raw_text", "token", "authorization"):
        with pytest.raises(Exception):
            WatcherEventIngestRequest.model_validate(_payload(**{forbidden: "rejected"}))


def test_company_resolution_is_exact_precedence_and_tenant_scoped(db_session) -> None:
    organization = _seed_org(db_session)
    company, _ = _seed_company_period(db_session, organization)
    company.nome_fantasia = "FANTASIA DIVERGENTE"
    db_session.flush()
    resolved, status = resolve_company(db_session, organization_id=organization.id, folder_company=" empresa   exemplo ")
    assert resolved is company and status is CompanyResolution.MATCHED
    assert resolve_company(db_session, organization_id=organization.id, folder_company="EMPRESA")[1] is CompanyResolution.UNMATCHED

    duplicate = ExternalCompany(
        organization_id=organization.id,
        cnpj="99999999999999",
        razao_social="OUTRA",
        apelido_pasta="EMPRESA EXEMPLO",
        active=True,
    )
    db_session.add(duplicate)
    db_session.flush()
    assert resolve_company(db_session, organization_id=organization.id, folder_company="EMPRESA EXEMPLO")[1] is CompanyResolution.AMBIGUOUS


@pytest.mark.parametrize("classifier_hint", ["DAS", "CSLL", "AMBIGUOUS"])
def test_ingest_keeps_filename_hint_out_of_canonical_evidence_and_replays_idempotently(db_session, classifier_hint: str) -> None:
    organization = _seed_org(db_session)
    company, period = _seed_company_period(db_session, organization)
    payload = WatcherEventIngestRequest.model_validate(_payload(classifier_hint=classifier_hint))
    first = ingest_watcher_event(db_session, organization=organization, payload=payload)
    replay = ingest_watcher_event(db_session, organization=organization, payload=payload)

    assert first.event_created and first.evidence_created
    assert first.event.company_id == company.id and first.event.period_id == period.id
    assert first.evidence is not None and first.evidence.watcher_event_id == first.event.id
    assert first.evidence.detected_tax is None
    assert first.evidence.detected_obligation is None
    assert first.event.raw_payload["classifier_hint"] == classifier_hint
    assert "classifier_hint" not in first.evidence.raw_payload
    assert not replay.event_created and not replay.evidence_created
    assert replay.event.id == first.event.id and replay.evidence is not None and replay.evidence.id == first.evidence.id
    assert db_session.scalar(select(AuditLog).where(AuditLog.event_type == "watcher.event.ingested")) is not None

    unresolved = WatcherEventIngestRequest.model_validate(_payload(
        relative_path=r"SEM MATCH\Escrita Fiscal\08-2026\Guias - Impostos e Parcelamentos\DAS 08-2026.pdf",
        file_name="DAS 08-2026.pdf",
        file_sha256="b" * 64,
        folder_company="SEM MATCH",
        folder_period="2026-08",
    ))
    result = ingest_watcher_event(db_session, organization=organization, payload=unresolved)
    assert result.event_created and result.evidence is None
    assert result.company_resolution is CompanyResolution.UNMATCHED
    assert result.period_resolution is PeriodResolution.PERIOD_NOT_FOUND


def test_idempotency_key_changes_for_path_or_hash_and_database_constraint_exists(db_session) -> None:
    organization = _seed_org(db_session)
    _seed_company_period(db_session, organization)
    first = ingest_watcher_event(db_session, organization=organization, payload=WatcherEventIngestRequest.model_validate(_payload()))
    different_hash = ingest_watcher_event(db_session, organization=organization, payload=WatcherEventIngestRequest.model_validate(_payload(file_sha256="c" * 64)))
    different_path = ingest_watcher_event(db_session, organization=organization, payload=WatcherEventIngestRequest.model_validate(_payload(
        relative_path=r"EMPRESA EXEMPLO\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\sub\DAS 07-2026.pdf",
        file_sha256="a" * 64,
    )))
    assert len({first.event.id, different_hash.event.id, different_path.event.id}) == 3
    with pytest.raises(IntegrityError):
        db_session.add(WatcherFileEvent(
            organization_id=organization.id, event_type="FILE_STABLE", file_path="x.pdf", file_name="x.pdf",
            idempotency_key=first.event.idempotency_key, status="PENDING",
        ))
        db_session.flush()


def test_evidence_is_visible_read_only_and_old_dominio_evidence_remains_unlinked(db_session) -> None:
    organization = _seed_org(db_session)
    company, period = _seed_company_period(db_session, organization)
    legacy = FiscalEvidence(
        organization_id=organization.id, company_id=company.id, period_id=period.id,
        source="DOMINIO_FOLHA_PDF", source_type="DOMINIO_PAYROLL_IMPORT", status="PENDENTE",
    )
    db_session.add(legacy)
    db_session.flush()
    ingest_watcher_event(db_session, organization=organization, payload=WatcherEventIngestRequest.model_validate(_payload()))
    response = lumen_read_model.get_evidences(db_session, organization_id=organization.id, competencia="2026-07", company_id=company.id)
    assert any(item.source == "WATCHER_FILE" for item in response.items)
    assert legacy.watcher_event_id is None


def test_endpoint_auth_fail_closed_and_response_is_sanitized(client, db_session, monkeypatch) -> None:
    organization = _seed_org(db_session)
    _seed_company_period(db_session, organization)
    response = client.post("/api/v1/lumen/evidences/watcher-event", json=_payload())
    assert response.status_code == 503

    headers = _configure_agent(monkeypatch, organization)
    assert client.post("/api/v1/lumen/evidences/watcher-event", json=_payload()).status_code == 401
    assert client.post("/api/v1/lumen/evidences/watcher-event", json=_payload(), headers={"X-Lumen-Agent-Token": "wrong"}).status_code == 401
    assert client.post("/api/v1/lumen/evidences/watcher-event", json=_payload(), headers={"Authorization": "Bearer human"}).status_code == 401

    created = client.post("/api/v1/lumen/evidences/watcher-event", json=_payload(), headers=headers)
    replay = client.post("/api/v1/lumen/evidences/watcher-event", json=_payload(), headers=headers)
    assert created.status_code == 200 and replay.status_code == 200
    assert created.json()["event_created"] and not replay.json()["event_created"]
    assert "synthetic-agent-token" not in str(created.json())


def test_endpoint_rejects_extra_payload_fields(client, db_session, monkeypatch) -> None:
    organization = _seed_org(db_session)
    _seed_company_period(db_session, organization)
    headers = _configure_agent(monkeypatch, organization)
    response = client.post("/api/v1/lumen/evidences/watcher-event", json=_payload(organization_id=999), headers=headers)
    assert response.status_code == 422


def test_migration_constraints_are_present(db_session) -> None:
    inspector = inspect(db_session.bind)
    watcher_unique = {constraint["name"] for constraint in inspector.get_unique_constraints("watcher_file_events")}
    evidence_unique = {constraint["name"] for constraint in inspector.get_unique_constraints("fiscal_evidences")}
    evidence_fks = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("fiscal_evidences")}
    assert "uq_watcher_file_events_idempotency_key" in watcher_unique
    assert "uq_fiscal_evidences_watcher_event_id" in evidence_unique
    assert "fk_fiscal_evidences_watcher_event_id" in evidence_fks
