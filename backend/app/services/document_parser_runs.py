"""Tenant-scoped persistence of versioned document parser executions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.fiscal_document_parser_run import FiscalDocumentParserRun
from backend.app.models.fiscal_evidence import FiscalEvidence
from backend.app.models.organization import Organization
from backend.app.schemas.watcher import WatcherParserRunRequest
from backend.app.services.audit import record_audit_event


class ParserRunEvidenceNotFound(LookupError):
    """The evidence is absent, out of tenant, or not owned by the Watcher."""


@dataclass(frozen=True, slots=True)
class ParserRunRegistration:
    parser_run: FiscalDocumentParserRun
    created: bool


def register_document_parser_run(
    session: Session,
    *,
    organization: Organization,
    evidence_id: int,
    payload: WatcherParserRunRequest,
) -> ParserRunRegistration:
    evidence = session.scalar(
        select(FiscalEvidence).where(
            FiscalEvidence.id == evidence_id,
            FiscalEvidence.organization_id == organization.id,
            FiscalEvidence.source == "WATCHER_FILE",
        )
    )
    if evidence is None:
        raise ParserRunEvidenceNotFound

    identity = (
        FiscalDocumentParserRun.organization_id == organization.id,
        FiscalDocumentParserRun.fiscal_evidence_id == evidence.id,
        FiscalDocumentParserRun.parser_name == payload.parser_name,
        FiscalDocumentParserRun.parser_version == payload.parser_version,
    )
    existing = session.scalar(select(FiscalDocumentParserRun).where(*identity))
    if existing is not None:
        return ParserRunRegistration(existing, False)

    parser_run = FiscalDocumentParserRun(
        organization_id=organization.id,
        fiscal_evidence_id=evidence.id,
        parser_name=payload.parser_name,
        parser_version=payload.parser_version,
        document_family=payload.document_family,
        extraction_status=payload.extraction_status,
        confidence=Decimal(str(payload.confidence)) if payload.confidence is not None else None,
        structured_payload={
            "signals": [signal.model_dump(mode="json") for signal in payload.signals],
            "structured_data": payload.structured_data,
        },
        warnings=payload.warnings,
    )
    try:
        with session.begin_nested():
            session.add(parser_run)
            session.flush()
    except IntegrityError as exc:
        if not _is_parser_run_identity_conflict(exc):
            raise
        existing = session.scalar(select(FiscalDocumentParserRun).where(*identity))
        if existing is None:
            raise
        return ParserRunRegistration(existing, False)

    record_audit_event(
        session,
        event_type="watcher.parser_run.registered",
        message="Watcher document parser run registered.",
        actor_type="WATCHER_AGENT",
        resource_type="fiscal_document_parser_run",
        resource_id=str(parser_run.id),
        event_metadata={
            "organization_id": organization.id,
            "evidence_id": evidence.id,
            "parser_name": parser_run.parser_name,
            "parser_version": parser_run.parser_version,
            "document_family": parser_run.document_family,
            "extraction_status": parser_run.extraction_status,
        },
    )
    return ParserRunRegistration(parser_run, True)


def _is_parser_run_identity_conflict(error: IntegrityError) -> bool:
    original = getattr(error, "orig", None)
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    return constraint_name == "uq_fiscal_doc_parser_runs_org_evidence_parser_version"
