from __future__ import annotations

from pathlib import Path

import pytest

from agent.watcher.file_detector import CandidateStatus, inspect_candidate


@pytest.mark.parametrize("name", ["DAS.pdf", "MIT.JSON", "nota.Xml", "documentos.ZIP"])
def test_supported_document_candidates_are_accepted(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.ACCEPTED


@pytest.mark.parametrize(
    "name", ["DAS.pdf.partial", "DAS.partial.pdf", "MIT.json.tmp", "arquivo.zip.crdownload", "~$DAS.pdf"]
)
def test_temporary_files_are_rejected(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.TEMPORARY


@pytest.mark.parametrize("name", ["DAS.txt", "DAS.docx", "DAS.xlsx", "DAS.jpg", "DAS.png"])
def test_unsupported_candidates_are_rejected(tmp_path: Path, name: str) -> None:
    assert inspect_candidate(tmp_path / name).status is CandidateStatus.UNSUPPORTED_EXTENSION


def test_directory_is_rejected(tmp_path: Path) -> None:
    assert inspect_candidate(tmp_path).status is CandidateStatus.DIRECTORY
