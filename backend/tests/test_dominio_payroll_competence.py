from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.integrations.dominio.competence import (
    map_payroll_to_assessment_competence,
    normalize_payroll_competence,
)


def test_map_payroll_to_assessment_competence_for_regular_month() -> None:
    mapped = map_payroll_to_assessment_competence("05/2026")
    assert mapped.payroll_competence == "2026-05"
    assert mapped.assessment_competence == "2026-06"
    assert mapped.source_payroll_competence == "2026-05"
    assert mapped.target_assessment_competence == "2026-06"


def test_map_payroll_to_assessment_competence_for_december_rollover() -> None:
    mapped = map_payroll_to_assessment_competence("12/2026")
    assert mapped.payroll_competence == "2026-12"
    assert mapped.assessment_competence == "2027-01"


def test_map_payroll_to_assessment_competence_for_january() -> None:
    mapped = map_payroll_to_assessment_competence("01/2026")
    assert mapped.payroll_competence == "2026-01"
    assert mapped.assessment_competence == "2026-02"


@pytest.mark.parametrize("value", ["00/2026", "13/2026", "05/26", "2026-05", "5/2026", "05-2026"])
def test_invalid_formats_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        map_payroll_to_assessment_competence(value)


def test_normalization_is_deterministic() -> None:
    first = normalize_payroll_competence("05/2026")
    second = normalize_payroll_competence("05/2026")
    assert first == second == "2026-05"


def test_competence_mapping_has_no_database_or_network_dependency() -> None:
    module_text = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "integrations"
        / "dominio"
        / "competence.py"
    ).read_text(encoding="utf-8")
    assert "sqlalchemy" not in module_text
    assert "requests" not in module_text
    assert "httpx" not in module_text
