"""Pure, filesystem-free grammar for the future fiscal watcher."""

from __future__ import annotations

import hashlib
import ntpath
import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable


_DIRECTORY_PERIOD_RE = re.compile(r"^(0[1-9]|1[0-2])-(\d{4})$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class WatcherPathError(ValueError):
    """Raised when a path cannot satisfy the fiscal watcher contract."""


@dataclass(frozen=True, slots=True)
class FiscalPath:
    relative_path: str
    normalized_relative_path: str
    folder_company: str
    folder_period: str
    folder_competence: str


def is_windows_reparse_point(path: Path) -> bool:
    """Return whether a filesystem entry is a Windows reparse point."""
    if os.name != "nt":
        return False
    attributes = path.lstat().st_file_attributes
    return bool(attributes & 0x400)


def normalize_relative_path(relative_path: str) -> str:
    """Return the canonical case-insensitive Windows relative path.

    This only normalizes lexical components. S10.1/S10.2 must additionally
    verify the resolved filesystem path and every reparse point against the
    configured allowlisted root.
    """
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("relative_path must be a non-empty string")

    candidate = relative_path.replace("/", "\\")
    if candidate.startswith("\\") or re.match(r"^[A-Za-z]:", candidate):
        raise ValueError("relative_path must not be absolute or UNC")

    parts: list[str] = []
    for part in candidate.split("\\"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError("relative_path escapes the allowlisted root")
            parts.pop()
            continue
        parts.append(part)

    if not parts:
        raise ValueError("relative_path must identify a file below the root")
    return "\\".join(parts).casefold()


def validate_fiscal_path_lexically(root: str | Path, absolute_file_path: str | Path) -> FiscalPath:
    """Validate the fixed fiscal grammar without touching the filesystem."""
    root_text = _normalize_windows_absolute(root, field="root")
    file_text = _normalize_windows_absolute(absolute_file_path, field="absolute_file_path")
    try:
        common = ntpath.commonpath([root_text.casefold(), file_text.casefold()])
    except ValueError as exc:
        raise WatcherPathError("absolute_file_path is outside the allowlisted root") from exc
    if common != root_text.casefold():
        raise WatcherPathError("absolute_file_path is outside the allowlisted root")

    relative_path = ntpath.relpath(file_text, root_text).replace("/", "\\")
    segments = [segment for segment in relative_path.split("\\") if segment not in ("", ".")]
    if any(segment == ".." for segment in segments):
        raise WatcherPathError("absolute_file_path escapes the allowlisted root")
    if len(segments) < 5:
        raise WatcherPathError("path does not satisfy the fiscal watcher grammar")
    if segments[1].casefold() != "escrita fiscal":
        raise WatcherPathError("path is missing the Escrita Fiscal segment")
    if segments[3].casefold() != "guias - impostos e parcelamentos":
        raise WatcherPathError("path is missing the Guias segment")

    folder_company = segments[0]
    folder_period = segments[2]
    folder_competence = folder_period_to_competence(folder_period)
    return FiscalPath(
        relative_path="\\".join(segments),
        normalized_relative_path=normalize_relative_path("\\".join(segments)),
        folder_company=folder_company,
        folder_period=folder_period,
        folder_competence=folder_competence,
    )


def validate_fiscal_path_physically(
    root: str | Path,
    absolute_file_path: str | Path,
    *,
    reparse_point_detector: Callable[[Path], bool] = is_windows_reparse_point,
) -> FiscalPath:
    """Reject links/reparse points and confirm the resolved file stays under root."""
    fiscal_path = validate_fiscal_path_lexically(root, absolute_file_path)
    root_path = Path(root)
    file_path = Path(absolute_file_path)
    if not root_path.exists() or not file_path.exists():
        raise WatcherPathError("root and candidate file must exist for physical validation")

    try:
        relative_native = file_path.relative_to(root_path)
    except ValueError as exc:
        raise WatcherPathError("absolute_file_path is outside the allowlisted root") from exc
    current = root_path
    for segment in relative_native.parts:
        if current.is_symlink() or reparse_point_detector(current):
            raise WatcherPathError("reparse point is not allowed in watcher path")
        current = current / segment
    if current.is_symlink() or reparse_point_detector(current):
        raise WatcherPathError("reparse point is not allowed in watcher path")

    resolved_root = root_path.resolve(strict=True)
    resolved_file = file_path.resolve(strict=True)
    try:
        resolved_file.relative_to(resolved_root)
    except ValueError as exc:
        raise WatcherPathError("resolved file escapes the allowlisted root") from exc
    return fiscal_path


def _normalize_windows_absolute(value: str | Path, *, field: str) -> str:
    candidate = str(value).replace("/", "\\")
    if not ntpath.isabs(candidate):
        raise WatcherPathError(f"{field} must be an absolute Windows path")
    return ntpath.normpath(candidate)


def folder_period_to_competence(folder_period: str) -> str:
    """Convert fiscal watcher folder grammar MM-AAAA into API grammar AAAA-MM."""
    match = _DIRECTORY_PERIOD_RE.fullmatch(folder_period)
    if match is None:
        raise ValueError("folder_period must use MM-AAAA")
    month, year = match.groups()
    return f"{year}-{month}"


def watcher_event_fingerprint(
    organization_id: int,
    relative_path: str,
    file_sha256: str,
) -> str:
    """Build the frozen logical-event identity without event_type."""
    if not isinstance(organization_id, int) or organization_id <= 0:
        raise ValueError("organization_id must be a positive integer")
    if _SHA256_RE.fullmatch(file_sha256) is None:
        raise ValueError("file_sha256 must be a SHA-256 hex digest")
    normalized_relative_path = normalize_relative_path(relative_path)
    source = f"{organization_id}\n{normalized_relative_path}\n{file_sha256.casefold()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
