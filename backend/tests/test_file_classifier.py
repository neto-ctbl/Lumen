from __future__ import annotations

import pytest

from agent.parsers.file_name_classifier import classify_file_name


@pytest.mark.parametrize(
    "hint",
    ["DAS", "PIS", "COFINS", "ICMS", "ISS", "DIFAL", "PROTEGE", "PGFN", "SISPAR", "PARC", "DCTFWEB", "DARF", "REINF", "MIT", "IRPJ", "CSLL"],
)
def test_all_keywords_are_classified_case_insensitively(hint: str) -> None:
    assert classify_file_name(f"guia_{hint.lower()}-sintetica.pdf") == hint


def test_filename_separators_equivalent_combination_unknown_and_ambiguity() -> None:
    assert classify_file_name("PARC (PGFN) - SISPAR.pdf") == "PGFN_SISPAR"
    assert classify_file_name("guia-sem-chave.pdf") == "UNKNOWN"
    assert classify_file_name("PIS COFINS.pdf") == "AMBIGUOUS"
