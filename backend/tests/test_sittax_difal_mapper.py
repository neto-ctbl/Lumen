from __future__ import annotations

import json
from pathlib import Path

from backend.app.services.integrations.sittax.mapper import map_difal_response


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_map_difal_response_with_guide() -> None:
    mapped = map_difal_response(_load("difal_with_guide.json"))

    assert mapped.difal_id == "difal-sint-001"
    assert mapped.has_guide is True
    assert mapped.dare_numbers == ["DARE-SINT-REV-001", "DARE-SINT-UCI-001"]
    assert mapped.total_purchases is not None
    assert mapped.message is None


def test_map_difal_response_without_guide_is_valid() -> None:
    mapped = map_difal_response(_load("difal_without_guide.json"))

    assert mapped.difal_id == "difal-sint-002"
    assert mapped.has_guide is False
    assert mapped.dare_numbers == []
    assert mapped.message == "Sem DIFAL devido para a competencia observada."
