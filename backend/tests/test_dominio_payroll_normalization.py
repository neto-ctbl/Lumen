from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services.integrations.dominio.contracts import (
    DominioCnpjStatus,
    DominioInformedValueKind,
)
from backend.app.services.integrations.dominio.normalization import (
    normalize_cnpj_for_dominio,
    normalize_search_text,
    parse_brazilian_date_to_iso,
    parse_brazilian_decimal,
    parse_competence_header_to_iso,
    parse_informed_value,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3.483,00", Decimal("3483.00")),
        ("1.621,00", Decimal("1621.00")),
        (",95", Decimal("0.95")),
        ("0,01", Decimal("0.01")),
        ("0,00", Decimal("0.00")),
    ],
)
def test_parse_brazilian_decimal_accepts_expected_formats(raw: str, expected: Decimal) -> None:
    assert parse_brazilian_decimal(raw) == expected


@pytest.mark.parametrize("raw", ["1,2", "1.2.3,00", "abc", "10", "1,000", "1,00x"])
def test_parse_brazilian_decimal_rejects_invalid_formats(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_brazilian_decimal(raw)


def test_parse_informed_value_handles_hours() -> None:
    parsed = parse_informed_value("220:00")
    assert parsed.kind == DominioInformedValueKind.HOURS
    assert parsed.minutes_value == 13200
    assert parsed.decimal_value is None


def test_parse_informed_value_handles_short_hours() -> None:
    parsed = parse_informed_value("7:20")
    assert parsed.kind == DominioInformedValueKind.HOURS
    assert parsed.minutes_value == 440


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("11,00", Decimal("11.00")),
        ("33,33", Decimal("33.33")),
        (",95", Decimal("0.95")),
        ("0,00", Decimal("0.00")),
    ],
)
def test_parse_informed_value_handles_generic_decimals(raw: str, expected: Decimal) -> None:
    parsed = parse_informed_value(raw)
    assert parsed.kind == DominioInformedValueKind.DECIMAL
    assert parsed.decimal_value == expected
    assert parsed.minutes_value is None


def test_parse_informed_value_preserves_unknown_values() -> None:
    parsed = parse_informed_value("11A")
    assert parsed.kind == DominioInformedValueKind.UNKNOWN
    assert parsed.raw == "11A"


def test_normalize_cnpj_for_dominio_accepts_valid_cnpj() -> None:
    parsed = normalize_cnpj_for_dominio("12.345.678/0001-95")
    assert parsed.status == DominioCnpjStatus.VALID
    assert parsed.normalized == "12345678000195"


def test_normalize_cnpj_for_dominio_marks_invalid_check_digits() -> None:
    parsed = normalize_cnpj_for_dominio("12.345.678/0001-00")
    assert parsed.status == DominioCnpjStatus.INVALID
    assert parsed.normalized == "12345678000100"
    assert parsed.is_digit_length_valid is True
    assert parsed.is_check_digits_valid is False


def test_normalize_cnpj_for_dominio_marks_invalid_length() -> None:
    parsed = normalize_cnpj_for_dominio("12.345.678/0001-9")
    assert parsed.status == DominioCnpjStatus.INVALID
    assert parsed.is_digit_length_valid is False


def test_parse_competence_header_to_iso() -> None:
    assert parse_competence_header_to_iso("05/2026") == "2026-05"


def test_parse_brazilian_date_to_iso() -> None:
    assert parse_brazilian_date_to_iso("07/06/2026") == "2026-06-07"


def test_normalize_search_text_is_ascii_and_deterministic() -> None:
    assert normalize_search_text("F.G.T.S  DO MÊS") == "f g t s do mes"
