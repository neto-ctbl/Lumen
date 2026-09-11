"""Incremental discovery constrained to authorized ``Escrita Fiscal`` roots."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from agent.watcher.file_detector import inspect_candidate
from agent.watcher.path_contract import (
    AuthorizedFiscalRoot,
    WatcherPathError,
    discover_authorized_fiscal_roots,
    is_windows_reparse_point,
    validate_document_path_physically,
)


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    path: Path
    normalized_relative_path: str
    size: int
    mtime_ns: int


def scan_fiscal_documents(root: str | Path) -> list[DiscoveredFile]:
    discovered: list[DiscoveredFile] = []
    for fiscal_root in discover_authorized_fiscal_roots(root):
        for candidate in _walk_without_links(fiscal_root):
            if not inspect_candidate(candidate).accepted:
                continue
            try:
                document_path = validate_document_path_physically(fiscal_root, candidate)
                stat = candidate.stat()
            except (OSError, WatcherPathError):
                continue
            discovered.append(
                DiscoveredFile(candidate, document_path.normalized_relative_path, stat.st_size, stat.st_mtime_ns)
            )
    return sorted(discovered, key=lambda item: item.normalized_relative_path)


def scan_fiscal_pdfs(root: str | Path) -> list[DiscoveredFile]:
    """Compatibility alias retained for S10 callers; discovery is now document-generic."""
    return scan_fiscal_documents(root)


def _walk_without_links(fiscal_root: AuthorizedFiscalRoot) -> list[Path]:
    files: list[Path] = []
    pending = [fiscal_root.path]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    try:
                        if entry.is_symlink() or is_windows_reparse_point(path):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(path)
                        elif entry.is_file(follow_symlinks=False):
                            files.append(path)
                    except OSError:
                        continue
        except OSError:
            continue
    return files
