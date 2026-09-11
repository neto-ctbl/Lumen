"""Fiscal watcher period grammar, deliberately independent from Dominio payroll."""

from __future__ import annotations

import re

from agent.watcher.path_contract import folder_period_to_competence


_PATH_PERIOD_RE = re.compile(r"^(0[1-9]|1[0-2])-(\d{4})$")


def period_candidates_from_segments(segments: list[str] | tuple[str, ...]) -> tuple[list[str], bool]:
    """Return distinct path-only period hints in first-observed order."""
    candidates: list[str] = []
    for segment in segments:
        match = _PATH_PERIOD_RE.fullmatch(segment.strip())
        if match is None:
            continue
        month, year = match.groups()
        normalized = f"{year}-{month}"
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates, len(candidates) > 1


def folder_period_from_path(folder_period: str) -> str:
    return folder_period_to_competence(folder_period)
