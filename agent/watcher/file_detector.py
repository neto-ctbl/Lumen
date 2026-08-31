"""Candidate filtering for an explicitly supplied local path."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CandidateStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DIRECTORY = "DIRECTORY"
    TEMPORARY = "TEMPORARY"
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"


@dataclass(frozen=True, slots=True)
class CandidateDecision:
    status: CandidateStatus

    @property
    def accepted(self) -> bool:
        return self.status is CandidateStatus.ACCEPTED


def inspect_candidate(path: str | Path) -> CandidateDecision:
    candidate = Path(path)
    name = candidate.name.casefold()
    if candidate.is_dir():
        return CandidateDecision(CandidateStatus.DIRECTORY)
    if name.startswith("~$") or name.endswith((".partial", ".tmp", ".crdownload")):
        return CandidateDecision(CandidateStatus.TEMPORARY)
    if candidate.suffix.casefold() != ".pdf":
        return CandidateDecision(CandidateStatus.UNSUPPORTED_EXTENSION)
    return CandidateDecision(CandidateStatus.ACCEPTED)
