"""Build a watcher-event v1 payload from one explicitly supplied local PDF."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent.parsers.file_name_classifier import classify_file_name
from agent.parsers.file_format_probe import probe_file_format
from agent.parsers.pdf_text_probe import probe_pdf_text
from agent.watcher.company_resolver import folder_company_from_path
from agent.watcher.file_detector import inspect_candidate
from agent.watcher.hash import sha256_file
from agent.watcher.path_contract import (
    WatcherPathError,
    resolve_authorized_fiscal_root,
    validate_document_path_physically,
    validate_fiscal_path_physically,
)
from agent.watcher.period_resolver import folder_period_from_path, period_candidates_from_segments


class PayloadBuildError(ValueError):
    pass


def build_watcher_event_payload(
    root: str | Path,
    absolute_file_path: str | Path,
    *,
    detected_at: datetime | None = None,
) -> dict[str, object]:
    """Build metadata only; no HTTP, database access or persistent state is used."""
    file_path = Path(absolute_file_path)
    decision = inspect_candidate(file_path)
    if not decision.accepted:
        raise PayloadBuildError(decision.status)
    try:
        fiscal_path = validate_fiscal_path_physically(root, file_path)
    except WatcherPathError as exc:
        raise PayloadBuildError(str(exc)) from exc

    before = file_path.stat()
    file_sha256 = sha256_file(file_path)
    pdf_probe = probe_pdf_text(file_path)
    after = file_path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise PayloadBuildError("FILE_CHANGED_DURING_PROCESSING")

    timestamp = detected_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise PayloadBuildError("detected_at must be timezone-aware")
    return {
        "schema_version": "1",
        "event_type": "FILE_STABLE",
        "relative_path": fiscal_path.relative_path,
        "file_name": file_path.name,
        "file_sha256": file_sha256,
        "file_size": before.st_size,
        "detected_at": timestamp.isoformat(),
        "folder_period": folder_period_from_path(fiscal_path.folder_period),
        "folder_company": folder_company_from_path(fiscal_path),
        "classifier_hint": classify_file_name(file_path.name),
        "pdf_probe": pdf_probe,
    }


def build_document_candidate_payload(
    root: str | Path,
    absolute_file_path: str | Path,
    *,
    detected_at: datetime | None = None,
) -> dict[str, object]:
    """Build the S11.0 v2 metadata payload without fiscal interpretation."""
    file_path = Path(absolute_file_path)
    decision = inspect_candidate(file_path)
    if not decision.accepted:
        raise PayloadBuildError(decision.status)
    try:
        fiscal_root = resolve_authorized_fiscal_root(root, file_path)
        document_path = validate_document_path_physically(fiscal_root, file_path)
    except WatcherPathError as exc:
        raise PayloadBuildError(str(exc)) from exc

    before = file_path.stat()
    file_sha256 = sha256_file(file_path)
    technical_probe = probe_file_format(file_path)
    after = file_path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise PayloadBuildError("FILE_CHANGED_DURING_PROCESSING")
    if not technical_probe["valid"]:
        raise PayloadBuildError("INVALID_FILE_FORMAT")

    timestamp = detected_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise PayloadBuildError("detected_at must be timezone-aware")
    periods, ambiguous = period_candidates_from_segments(list(document_path.segments_below_fiscal_root))
    return {
        "contract_version": 2,
        "event": {"event_type": "FILE_STABLE", "detected_at": timestamp.isoformat()},
        "file": {
            "relative_path": document_path.relative_path,
            "file_name": file_path.name,
            "extension": file_path.suffix.casefold(),
            "size": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "sha256": file_sha256,
        },
        "path_context": {
            "enterprise_folder_candidate": document_path.enterprise_folder_candidate,
            "fiscal_root": "Escrita Fiscal",
            "segments_below_fiscal_root": list(document_path.segments_below_fiscal_root),
            "period_candidates": periods,
            "period_ambiguous": ambiguous,
            "classifier_hint": classify_file_name(file_path.name),
        },
        "technical_probe": technical_probe,
    }
