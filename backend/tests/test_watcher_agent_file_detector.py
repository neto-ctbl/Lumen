from __future__ import annotations

from pathlib import Path

import pytest

from agent.watcher.file_detector import CandidateStatus, inspect_candidate


@pytest.mark.parametrize("name", ["DAS.pdf", "DAS.PDF", "guia.PdF"])
def test_pdf_candidates_are_accepted(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.ACCEPTED


@pytest.mark.parametrize("name", ["DAS.pdf.partial", "DAS.pdf.tmp", "DAS.pdf.crdownload", "~$DAS.pdf"])
def test_temporary_files_are_rejected(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.TEMPORARY


@pytest.mark.parametrize("name", ["DAS.xml", "DAS.txt", "DAS.docx", "DAS.xlsx", "DAS.zip", "DAS.jpg", "DAS.png"])
def test_non_pdf_candidates_are_rejected(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.UNSUPPORTED_EXTENSION


def test_directory_is_rejected(tmp_path: Path) -> None:
    assert inspect_candidate(tmp_path).status is CandidateStatus.DIRECTORY
