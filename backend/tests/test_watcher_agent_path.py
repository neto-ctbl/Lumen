from __future__ import annotations

from pathlib import Path

import pytest

from agent.watcher.path_contract import WatcherPathError, validate_fiscal_path_lexically, validate_fiscal_path_physically
from agent.watcher.company_resolver import folder_company_from_path
from agent.watcher.period_resolver import folder_period_from_path
from backend.tests.watcher_agent_test_utils import watcher_pdf_path, write_synthetic_pdf


def test_canonical_and_nested_paths_are_accepted_case_insensitively(tmp_path: Path) -> None:
    file_path = watcher_pdf_path(tmp_path, nested=True)
    write_synthetic_pdf(file_path)
    result = validate_fiscal_path_physically(tmp_path, file_path)
    lexical = validate_fiscal_path_lexically(str(tmp_path).upper(), str(file_path).upper())

    assert result.folder_company == "EMPRESA EXEMPLO"
    assert result.folder_competence == "2026-07"
    assert result.normalized_relative_path == lexical.normalized_relative_path
    assert result.relative_path.endswith(r"Federais\DAS 07-2026.pdf")
    assert folder_company_from_path(result) == "EMPRESA EXEMPLO"


@pytest.mark.parametrize(("folder", "competence"), [("01-2026", "2026-01"), ("07-2026", "2026-07"), ("12-2026", "2026-12")])
def test_period_resolution_is_folder_only_without_payroll_offset(folder: str, competence: str) -> None:
    assert folder_period_from_path(folder) == competence


@pytest.mark.parametrize("folder", ["00-2026", "13-2026", "7-2026", "07/2026", "2026-07"])
def test_invalid_folder_period_is_rejected(folder: str) -> None:
    with pytest.raises(ValueError):
        folder_period_from_path(folder)


@pytest.mark.parametrize(
    "parts",
    [
        ("EMPRESA EXEMPLO", "Escrita Fiscal", "Importação", "Saída", "arquivo.pdf"),
        ("EMPRESA EXEMPLO", "Documentos", "arquivo.pdf"),
        ("EMPRESA EXEMPLO", "07-2026", "Guias - Impostos e Parcelamentos", "arquivo.pdf"),
        ("EMPRESA EXEMPLO", "Escrita Fiscal", "07-2026", "Outro", "arquivo.pdf"),
    ],
)
def test_invalid_fiscal_grammar_is_rejected(tmp_path: Path, parts: tuple[str, ...]) -> None:
    candidate = tmp_path.joinpath(*parts)
    with pytest.raises(WatcherPathError):
        validate_fiscal_path_lexically(tmp_path, candidate)


def test_outside_root_and_traversal_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.pdf"
    with pytest.raises(WatcherPathError):
        validate_fiscal_path_lexically(tmp_path, outside)
    with pytest.raises(WatcherPathError):
        validate_fiscal_path_lexically(tmp_path, tmp_path / ".." / "outside.pdf")


def test_physical_guard_rejects_injected_reparse_point(tmp_path: Path) -> None:
    file_path = watcher_pdf_path(tmp_path)
    write_synthetic_pdf(file_path)
    with pytest.raises(WatcherPathError, match="reparse"):
        validate_fiscal_path_physically(tmp_path, file_path, reparse_point_detector=lambda path: path == file_path)
