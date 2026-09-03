from __future__ import annotations

from sqlalchemy import func, select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherEventIngestRequest
from backend.app.services.watcher_ingest import ingest_watcher_event
from backend.app.services.watcher_reprocess import reprocess_unresolved_watcher_events


def _organization(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _company(db_session, organization: Organization, alias: str) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=f"{organization.id:010d}{len(alias):04d}",
        razao_social=f"{alias} LTDA",
        nome_fantasia=alias,
        apelido_pasta=alias,
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    return company


def _period(db_session, organization: Organization) -> FiscalPeriod:
    period = FiscalPeriod(organization_id=organization.id, year=2026, month=7, competencia="2026-07", status="OPEN")
    db_session.add(period)
    db_session.flush()
    return period


def _payload(*, company: str, file_sha256: str) -> WatcherEventIngestRequest:
    return WatcherEventIngestRequest.model_validate({
        "schema_version": "1", "event_type": "FILE_STABLE",
        "relative_path": rf"{company}\Escrita Fiscal\07-2026\Guias - Impostos e Parcelamentos\guia.pdf",
        "file_name": "guia.pdf", "file_sha256": file_sha256, "file_size": 1,
        "detected_at": "2026-09-03T12:00:00+00:00", "folder_period": "2026-07", "folder_company": company,
        "classifier_hint": "DAS", "pdf_probe": {"is_pdf": True, "page_count": 1, "has_extractable_text": True, "text_length": 1},
    })


def _evidence_count(db_session, event_id: int) -> int:
    return db_session.scalar(select(func.count()).select_from(FiscalEvidence).where(FiscalEvidence.watcher_event_id == event_id)) or 0


def test_reprocess_keeps_unmatched_ambiguous_and_missing_period_without_evidence(db_session) -> None:
    unmatched_org = _organization(db_session, "reprocess-unmatched")
    _period(db_session, unmatched_org)
    unmatched = ingest_watcher_event(db_session, organization=unmatched_org, payload=_payload(company="UNKNOWN", file_sha256="a" * 64)).event
    assert reprocess_unresolved_watcher_events(db_session, organization=unmatched_org).unresolved == 1
    assert _evidence_count(db_session, unmatched.id) == 0

    ambiguous_org = _organization(db_session, "reprocess-ambiguous")
    _period(db_session, ambiguous_org)
    _company(db_session, ambiguous_org, "DUPLICADA")
    second = _company(db_session, ambiguous_org, "OUTRA")
    second.apelido_pasta = "DUPLICADA"
    ambiguous = ingest_watcher_event(db_session, organization=ambiguous_org, payload=_payload(company="DUPLICADA", file_sha256="b" * 64)).event
    assert reprocess_unresolved_watcher_events(db_session, organization=ambiguous_org).unresolved == 1
    assert _evidence_count(db_session, ambiguous.id) == 0

    missing_period_org = _organization(db_session, "reprocess-period")
    _company(db_session, missing_period_org, "SEM PERIODO")
    missing_period = ingest_watcher_event(db_session, organization=missing_period_org, payload=_payload(company="SEM PERIODO", file_sha256="c" * 64)).event
    assert reprocess_unresolved_watcher_events(db_session, organization=missing_period_org).unresolved == 1
    assert _evidence_count(db_session, missing_period.id) == 0


def test_reprocess_resolves_later_once_without_changing_obligation_statuses(db_session) -> None:
    organization = _organization(db_session, "reprocess-later")
    _period(db_session, organization)
    event = ingest_watcher_event(db_session, organization=organization, payload=_payload(company="LATER", file_sha256="d" * 64)).event
    before = db_session.scalar(select(func.count()).select_from(FiscalObligationStatus))
    company = _company(db_session, organization, "LATER")

    first = reprocess_unresolved_watcher_events(db_session, organization=organization)
    second = reprocess_unresolved_watcher_events(db_session, organization=organization)
    evidence = db_session.scalar(select(FiscalEvidence).where(FiscalEvidence.watcher_event_id == event.id))

    assert first.evidence_created == 1 and second.evidence_created == 0
    assert evidence is not None and evidence.company_id == company.id
    assert evidence.source == "WATCHER_FILE" and evidence.watcher_event_id == event.id
    assert evidence.detected_tax is None and evidence.detected_obligation is None
    assert _evidence_count(db_session, event.id) == 1
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == before


def test_reprocess_does_not_cross_organization_boundaries(db_session) -> None:
    source_org = _organization(db_session, "reprocess-source")
    _period(db_session, source_org)
    event = ingest_watcher_event(db_session, organization=source_org, payload=_payload(company="ISOLATED", file_sha256="e" * 64)).event
    other_org = _organization(db_session, "reprocess-other")
    _period(db_session, other_org)
    _company(db_session, other_org, "ISOLATED")

    result = reprocess_unresolved_watcher_events(db_session, organization=other_org)
    assert result.inspected == 0
    assert _evidence_count(db_session, event.id) == 0
