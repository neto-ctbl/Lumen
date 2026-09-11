"""Server-side ingest for metadata-only fiscal watcher events."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PureWindowsPath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.app.models.watcher_file_event import WatcherFileEvent
from backend.app.schemas.watcher import WatcherDocumentCandidateRequest, WatcherEventIngestRequest, WatcherIngestRequest
from backend.app.services.audit import record_audit_event


class WatcherIngestError(ValueError):
    pass


class CompanyResolution(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    CANDIDATE_ONLY = "CANDIDATE_ONLY"


class PeriodResolution(str, Enum):
    MATCHED = "MATCHED"
    PERIOD_NOT_FOUND = "PERIOD_NOT_FOUND"
    NO_CANDIDATE = "NO_CANDIDATE"
    CANDIDATE_ONLY = "CANDIDATE_ONLY"
    AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"


@dataclass(frozen=True, slots=True)
class SemanticWatcherEvent:
    relative_path: str
    normalized_relative_path: str
    folder_company: str
    folder_period: str


@dataclass(frozen=True, slots=True)
class SemanticDocumentCandidate:
    relative_path: str
    normalized_relative_path: str


@dataclass(frozen=True, slots=True)
class WatcherIngestResult:
    event: WatcherFileEvent
    evidence: FiscalEvidence | None
    event_created: bool
    evidence_created: bool
    company_resolution: CompanyResolution
    period_resolution: PeriodResolution


def ingest_watcher_event(
    session: Session,
    *,
    organization: Organization,
    payload: WatcherIngestRequest,
) -> WatcherIngestResult:
    if isinstance(payload, WatcherDocumentCandidateRequest):
        return _ingest_document_candidate(session, organization=organization, payload=payload)
    semantic = validate_watcher_event_semantics(payload)
    company, company_resolution = resolve_company(session, organization_id=organization.id, folder_company=semantic.folder_company)
    period, period_resolution = resolve_period(session, organization_id=organization.id, folder_period=semantic.folder_period)
    idempotency_key = watcher_idempotency_key(organization.id, semantic.normalized_relative_path, payload.file_sha256)

    existing = session.scalar(select(WatcherFileEvent).where(WatcherFileEvent.idempotency_key == idempotency_key))
    if existing is not None:
        return _replay_result(session, existing)

    safe_payload = payload.model_dump(mode="json")
    safe_payload["_lumen_resolution"] = {
        "company": company_resolution.value,
        "period": period_resolution.value,
    }
    event = WatcherFileEvent(
        organization_id=organization.id,
        company_id=company.id if company is not None else None,
        period_id=period.id if period is not None else None,
        event_type=payload.event_type,
        file_path=semantic.relative_path,
        normalized_relative_path=semantic.normalized_relative_path,
        idempotency_key=idempotency_key,
        file_name=payload.file_name,
        file_hash=payload.file_sha256.casefold(),
        file_size=payload.file_size,
        detected_at=payload.detected_at,
        status="PENDING",
        raw_payload=safe_payload,
    )
    try:
        with session.begin_nested():
            session.add(event)
            session.flush()
    except IntegrityError as exc:
        if not _is_idempotency_conflict(exc):
            raise
        existing = session.scalar(select(WatcherFileEvent).where(WatcherFileEvent.idempotency_key == idempotency_key))
        if existing is None:
            raise
        return _replay_result(session, existing)

    evidence, evidence_created = link_watcher_event_to_document_evidence(
        session,
        event=event,
        company_id=company.id if company is not None else None,
        period_id=period.id if period is not None else None,
        provenance={
            "schema_version": payload.schema_version,
            "pdf_probe": payload.pdf_probe.model_dump(),
        },
    )

    record_audit_event(
        session,
        event_type="watcher.event.ingested",
        message="Watcher event ingested.",
        actor_type="WATCHER_AGENT",
        resource_type="watcher_file_event",
        resource_id=str(event.id),
        event_metadata={
            "watcher_event_id": event.id,
            "evidence_id": evidence.id if evidence is not None else None,
            "evidence_created": evidence_created,
            "company_resolution": company_resolution.value,
            "period_resolution": period_resolution.value,
            "classifier_hint": payload.classifier_hint,
        },
    )
    return WatcherIngestResult(event, evidence, True, evidence_created, company_resolution, period_resolution)


def _ingest_document_candidate(
    session: Session,
    *,
    organization: Organization,
    payload: WatcherDocumentCandidateRequest,
) -> WatcherIngestResult:
    semantic = validate_document_candidate_semantics(payload)
    company_resolution = CompanyResolution.CANDIDATE_ONLY
    if payload.path_context.period_ambiguous:
        period_resolution = PeriodResolution.AMBIGUOUS_CANDIDATES
    elif payload.path_context.period_candidates:
        period_resolution = PeriodResolution.CANDIDATE_ONLY
    else:
        period_resolution = PeriodResolution.NO_CANDIDATE
    idempotency_key = watcher_idempotency_key(organization.id, semantic.normalized_relative_path, payload.file.sha256)
    existing = session.scalar(select(WatcherFileEvent).where(WatcherFileEvent.idempotency_key == idempotency_key))
    if existing is not None:
        return _replay_result(session, existing)

    safe_payload = payload.model_dump(mode="json")
    safe_payload["_lumen_resolution"] = {
        "company": company_resolution.value,
        "period": period_resolution.value,
    }
    event = WatcherFileEvent(
        organization_id=organization.id,
        company_id=None,
        period_id=None,
        event_type=payload.event.event_type,
        file_path=semantic.relative_path,
        normalized_relative_path=semantic.normalized_relative_path,
        idempotency_key=idempotency_key,
        file_name=payload.file.file_name,
        file_hash=payload.file.sha256.casefold(),
        file_size=payload.file.size,
        detected_at=payload.event.detected_at,
        status="PENDING",
        raw_payload=safe_payload,
    )
    try:
        with session.begin_nested():
            session.add(event)
            session.flush()
    except IntegrityError as exc:
        if not _is_idempotency_conflict(exc):
            raise
        existing = session.scalar(select(WatcherFileEvent).where(WatcherFileEvent.idempotency_key == idempotency_key))
        if existing is None:
            raise
        return _replay_result(session, existing)

    evidence, evidence_created = link_watcher_event_to_document_evidence(
        session,
        event=event,
        company_id=None,
        period_id=None,
        provenance={
            "contract_version": payload.contract_version,
            "technical_probe": payload.technical_probe.model_dump(),
            "path_context": payload.path_context.model_dump(),
        },
    )
    record_audit_event(
        session,
        event_type="watcher.event.ingested",
        message="Watcher document candidate ingested.",
        actor_type="WATCHER_AGENT",
        resource_type="watcher_file_event",
        resource_id=str(event.id),
        event_metadata={
            "watcher_event_id": event.id,
            "evidence_id": evidence.id,
            "evidence_created": evidence_created,
            "contract_version": 2,
            "company_resolution": company_resolution.value,
            "period_resolution": period_resolution.value,
            "extension": payload.file.extension,
            "classifier_hint": payload.path_context.classifier_hint,
        },
    )
    return WatcherIngestResult(event, evidence, True, evidence_created, company_resolution, period_resolution)


def validate_document_candidate_semantics(payload: WatcherDocumentCandidateRequest) -> SemanticDocumentCandidate:
    path = PureWindowsPath(payload.file.relative_path)
    if path.is_absolute() or path.drive or path.root or ".." in path.parts:
        raise WatcherIngestError("relative_path must be a relative Windows path")
    parts = [part for part in path.parts if part not in (".", "")]
    if len(parts) < 3 or parts[1].casefold() != "escrita fiscal":
        raise WatcherIngestError("relative_path must be below an immediate Escrita Fiscal root")
    if path.name.casefold() != payload.file.file_name.casefold():
        raise WatcherIngestError("file_name must match the relative path leaf")
    if path.suffix.casefold() != payload.file.extension:
        raise WatcherIngestError("extension must match the relative path leaf")
    context = payload.path_context
    if _normalize_name(parts[0]) != _normalize_name(context.enterprise_folder_candidate):
        raise WatcherIngestError("enterprise folder candidate does not match relative_path")
    if [part.casefold() for part in parts[2:-1]] != [part.casefold() for part in context.segments_below_fiscal_root]:
        raise WatcherIngestError("path segments do not match relative_path")

    period_candidates: list[str] = []
    for segment in parts[2:-1]:
        match = re.fullmatch(r"(0[1-9]|1[0-2])-(\d{4})", segment.strip())
        if match is not None:
            month, year = match.groups()
            normalized = f"{year}-{month}"
            if normalized not in period_candidates:
                period_candidates.append(normalized)
    if period_candidates != context.period_candidates or context.period_ambiguous != (len(period_candidates) > 1):
        raise WatcherIngestError("period candidates do not match relative_path")

    expected_format = {".pdf": "PDF", ".json": "JSON", ".xml": "XML", ".zip": "ZIP"}[payload.file.extension]
    if not payload.technical_probe.valid or payload.technical_probe.format != expected_format:
        raise WatcherIngestError("technical probe does not match the file extension")
    relative_path = "\\".join(parts)
    return SemanticDocumentCandidate(relative_path, _normalize_relative_path(relative_path))


def validate_watcher_event_semantics(payload: WatcherEventIngestRequest) -> SemanticWatcherEvent:
    path = PureWindowsPath(payload.relative_path)
    if path.is_absolute() or path.drive or path.root or ".." in path.parts:
        raise WatcherIngestError("relative_path must be a relative Windows path")
    parts = [part for part in path.parts if part not in (".", "")]
    if len(parts) < 5 or parts[1].casefold() != "escrita fiscal" or parts[3].casefold() != "guias - impostos e parcelamentos":
        raise WatcherIngestError("relative_path does not satisfy the fiscal watcher grammar")
    if path.name.casefold() != payload.file_name.casefold() or path.suffix.casefold() != ".pdf":
        raise WatcherIngestError("file_name must match a PDF path leaf")
    folder_company = parts[0]
    if _normalize_name(folder_company) != _normalize_name(payload.folder_company):
        raise WatcherIngestError("folder_company does not match relative_path")
    folder_period = parts[2]
    if len(folder_period) != 7 or folder_period[2] != "-":
        raise WatcherIngestError("relative_path folder period is invalid")
    month, year = folder_period.split("-", maxsplit=1)
    if not month.isdigit() or not year.isdigit() or not 1 <= int(month) <= 12:
        raise WatcherIngestError("relative_path folder period is invalid")
    if f"{year}-{month}" != payload.folder_period:
        raise WatcherIngestError("folder_period does not match relative_path")
    relative_path = "\\".join(parts)
    return SemanticWatcherEvent(relative_path, _normalize_relative_path(relative_path), folder_company, payload.folder_period)


def resolve_company(session: Session, *, organization_id: int, folder_company: str) -> tuple[ExternalCompany | None, CompanyResolution]:
    companies = list(session.scalars(select(ExternalCompany).where(
        ExternalCompany.organization_id == organization_id,
        ExternalCompany.active.is_(True),
    )))
    expected = _normalize_name(folder_company)
    for attribute in ("apelido_pasta", "nome_fantasia", "razao_social"):
        matches = [company for company in companies if _normalize_name(getattr(company, attribute)) == expected]
        if len(matches) == 1:
            return matches[0], CompanyResolution.MATCHED
        if len(matches) > 1:
            return None, CompanyResolution.AMBIGUOUS
    return None, CompanyResolution.UNMATCHED


def resolve_period(session: Session, *, organization_id: int, folder_period: str) -> tuple[FiscalPeriod | None, PeriodResolution]:
    period = session.scalar(select(FiscalPeriod).where(
        FiscalPeriod.organization_id == organization_id,
        FiscalPeriod.competencia == folder_period,
    ))
    return (period, PeriodResolution.MATCHED) if period is not None else (None, PeriodResolution.PERIOD_NOT_FOUND)


def watcher_idempotency_key(organization_id: int, normalized_relative_path: str, file_sha256: str) -> str:
    source = f"{organization_id}\n{normalized_relative_path}\n{file_sha256.casefold()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def link_watcher_event_to_document_evidence(
    session: Session,
    *,
    event: WatcherFileEvent,
    company_id: int | None,
    period_id: int | None,
    provenance: dict[str, object],
) -> tuple[FiscalEvidence, bool]:
    """Link one physical event to the tenant-scoped canonical evidence for its content."""
    if event.id is None or not event.file_hash:
        raise WatcherIngestError("watcher event requires a persisted SHA-256")
    normalized_hash = event.file_hash.casefold()
    event.file_hash = normalized_hash
    existing = _watcher_evidence_by_identity(
        session,
        organization_id=event.organization_id,
        file_hash=normalized_hash,
    )
    if existing is not None:
        event.evidence_id = existing.id
        session.flush()
        return existing, False

    evidence = FiscalEvidence(
        organization_id=event.organization_id,
        company_id=company_id,
        period_id=period_id,
        watcher_event_id=event.id,
        source="WATCHER_FILE",
        source_type="WATCHER_INGEST",
        # This is intentionally the first observed path, not a canonical current location.
        file_path=event.normalized_relative_path,
        file_hash=normalized_hash,
        file_name=event.file_name,
        raw_payload={**provenance, "first_watcher_event_id": event.id},
        status="PENDENTE",
    )
    try:
        with session.begin_nested():
            session.add(evidence)
            session.flush()
            event.evidence_id = evidence.id
            session.flush()
    except IntegrityError as exc:
        if not _is_document_identity_conflict(exc):
            raise
        existing = _watcher_evidence_by_identity(
            session,
            organization_id=event.organization_id,
            file_hash=normalized_hash,
        )
        if existing is None:
            raise
        event.evidence_id = existing.id
        session.flush()
        return existing, False
    return evidence, True


def _watcher_evidence_by_identity(
    session: Session,
    *,
    organization_id: int,
    file_hash: str,
) -> FiscalEvidence | None:
    return session.scalar(
        select(FiscalEvidence).where(
            FiscalEvidence.organization_id == organization_id,
            FiscalEvidence.source == "WATCHER_FILE",
            FiscalEvidence.file_hash == file_hash,
        )
    )


def _replay_result(session: Session, event: WatcherFileEvent) -> WatcherIngestResult:
    evidence = session.get(FiscalEvidence, event.evidence_id) if event.evidence_id is not None else None
    if evidence is None:
        # Compatibility for pre-S11.0.1 rows before the migration backfill runs.
        evidence = session.scalar(select(FiscalEvidence).where(FiscalEvidence.watcher_event_id == event.id))
    resolution = event.raw_payload.get("_lumen_resolution", {}) if event.raw_payload else {}
    return WatcherIngestResult(
        event,
        evidence,
        False,
        False,
        CompanyResolution(resolution.get("company", CompanyResolution.UNMATCHED.value)),
        PeriodResolution(resolution.get("period", PeriodResolution.PERIOD_NOT_FOUND.value)),
    )


def _normalize_name(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _normalize_relative_path(value: str) -> str:
    return "\\".join(part.casefold() for part in PureWindowsPath(value).parts if part not in (".", ""))


def _is_idempotency_conflict(error: IntegrityError) -> bool:
    original = getattr(error, "orig", None)
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    return constraint_name == "uq_watcher_file_events_idempotency_key"


def _is_document_identity_conflict(error: IntegrityError) -> bool:
    original = getattr(error, "orig", None)
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    return constraint_name == "uq_fiscal_evidences_watcher_org_source_hash"
