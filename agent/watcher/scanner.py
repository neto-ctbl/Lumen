"""Incremental filesystem discovery constrained to the fiscal watcher grammar."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.watcher.file_detector import inspect_candidate
from agent.watcher.path_contract import WatcherPathError, validate_fiscal_path_physically


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    path: Path
    normalized_relative_path: str
    size: int
    mtime_ns: int


def scan_fiscal_pdfs(root: str | Path) -> list[DiscoveredFile]:
    root_path = Path(root)
    if not root_path.is_dir():
        raise FileNotFoundError("watcher root is unavailable")

    discovered: list[DiscoveredFile] = []
    for candidate in root_path.rglob("*"):
        if not inspect_candidate(candidate).accepted:
            continue
        try:
            fiscal_path = validate_fiscal_path_physically(root_path, candidate)
            stat = candidate.stat()
        except (OSError, WatcherPathError):
            continue
        discovered.append(DiscoveredFile(candidate, fiscal_path.normalized_relative_path, stat.st_size, stat.st_mtime_ns))
    return sorted(discovered, key=lambda item: item.normalized_relative_path)
