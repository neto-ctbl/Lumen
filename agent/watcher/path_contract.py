"""Pure, filesystem-free grammar for the future fiscal watcher."""

from __future__ import annotations

import hashlib
import re


_DIRECTORY_PERIOD_RE = re.compile(r"^(0[1-9]|1[0-2])-(\d{4})$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


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
