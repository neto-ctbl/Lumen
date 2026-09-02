"""Server-side ingest for metadata-only fiscal watcher events."""

from __future__ import annotations

import hashlib
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
from backend.app.schemas.watcher import WatcherEventIngestRequest
from backend.app.services.audit import record_audit_event


class WatcherIngestError(ValueError):
    pass


class CompanyResolution(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"


class PeriodResolution(str, Enum):
    MATCHED = "MATCHED"
    PERIOD_NOT_FOUND = "PERIOD_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class SemanticWatcherEvent:
    relative_path: str
    normalized_relative_path: str
    folder_company: str
    folder_period: str


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
    payload: WatcherEventIngestRequest,
) -> WatcherIngestResult:
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

    evidence = None
    evidence_created = False
    if company is not None and period is not None:
        evidence = FiscalEvidence(
            organization_id=organization.id,
            company_id=company.id,
            period_id=period.id,
            watcher_event_id=event.id,
            source="WATCHER_FILE",
            source_type="WATCHER_INGEST",
            file_path=semantic.normalized_relative_path,
            file_hash=payload.file_sha256.casefold(),
            file_name=payload.file_name,
            raw_payload={
                "schema_version": payload.schema_version,
                "pdf_probe": payload.pdf_probe.model_dump(),
                "watcher_event_id": event.id,
            },
            status="PENDENTE",
        )
        session.add(evidence)
        session.flush()
        evidence_created = True

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
            "company_resolution": company_resolution.value,
            "period_resolution": period_resolution.value,
            "classifier_hint": payload.classifier_hint,
        },
    )
    return WatcherIngestResult(event, evidence, True, evidence_created, company_resolution, period_resolution)


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


def _replay_result(session: Session, event: WatcherFileEvent) -> WatcherIngestResult:
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
