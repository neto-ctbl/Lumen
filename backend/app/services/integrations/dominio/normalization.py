from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from unidecode import unidecode

from backend.app.services.integrations.dominio.contracts import (
    DominioCnpjStatus,
    DominioInformedValueKind,
)
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj


BRAZILIAN_DECIMAL_RE = re.compile(r"^(?:\d{1,3}(?:\.\d{3})*|\d+|),\d{2}$")
HOURS_RE = re.compile(r"^(?P<hours>\d{1,4}):(?P<minutes>\d{2})$")
BLOCK_COMPETENCE_RE = re.compile(r"(?P<month>0[1-9]|1[0-2])/(?P<year>\d{4})")
DATE_RE = re.compile(r"^(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})$")


@dataclass(frozen=True, slots=True)
class DominioParsedInformedValue:
    raw: str
    kind: DominioInformedValueKind
    decimal_value: Decimal | None
    minutes_value: int | None


@dataclass(frozen=True, slots=True)
class DominioNormalizedCnpj:
    raw: str | None
    normalized: str | None
    status: DominioCnpjStatus
    is_digit_length_valid: bool
    is_check_digits_valid: bool


def normalize_dominio_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalize_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unidecode(normalize_dominio_text(value)).lower()).strip()


def parse_brazilian_decimal(value: str) -> Decimal:
    text = normalize_dominio_text(value)
    if not BRAZILIAN_DECIMAL_RE.fullmatch(text):
        raise ValueError(f"Invalid Brazilian decimal value: {value!r}")
    normalized = text.replace(".", "")
    if normalized.startswith(","):
        normalized = f"0{normalized}"
    try:
        return Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal payload: {value!r}") from exc


def parse_informed_value(value: str) -> DominioParsedInformedValue:
    text = normalize_dominio_text(value)
    hours_match = HOURS_RE.fullmatch(text)
    if hours_match is not None:
        hours = int(hours_match.group("hours"))
        minutes = int(hours_match.group("minutes"))
        if minutes >= 60:
            return DominioParsedInformedValue(
                raw=text,
                kind=DominioInformedValueKind.UNKNOWN,
                decimal_value=None,
                minutes_value=None,
            )
        return DominioParsedInformedValue(
            raw=text,
            kind=DominioInformedValueKind.HOURS,
            decimal_value=None,
            minutes_value=(hours * 60) + minutes,
        )

    try:
        decimal_value = parse_brazilian_decimal(text)
    except ValueError:
        return DominioParsedInformedValue(
            raw=text,
            kind=DominioInformedValueKind.UNKNOWN,
            decimal_value=None,
            minutes_value=None,
        )

    return DominioParsedInformedValue(
        raw=text,
        kind=DominioInformedValueKind.DECIMAL,
        decimal_value=decimal_value,
        minutes_value=None,
    )


def normalize_cnpj_for_dominio(value: Any) -> DominioNormalizedCnpj:
    raw = normalize_dominio_text(value) or None
    if raw is None:
        return DominioNormalizedCnpj(
            raw=None,
            normalized=None,
            status=DominioCnpjStatus.MISSING,
            is_digit_length_valid=False,
            is_check_digits_valid=False,
        )

    normalized = normalize_cnpj(raw)
    digits = "".join(ch for ch in raw if ch.isdigit())
    if normalized is None or len(digits) == 0:
        return DominioNormalizedCnpj(
            raw=raw,
            normalized=normalized,
            status=DominioCnpjStatus.MISSING,
            is_digit_length_valid=False,
            is_check_digits_valid=False,
        )

    if len(digits) != 14:
        return DominioNormalizedCnpj(
            raw=raw,
            normalized=normalized,
            status=DominioCnpjStatus.INVALID,
            is_digit_length_valid=False,
            is_check_digits_valid=False,
        )

    is_check_digits_valid = _validate_cnpj_check_digits(digits)
    return DominioNormalizedCnpj(
        raw=raw,
        normalized=digits,
        status=DominioCnpjStatus.VALID if is_check_digits_valid else DominioCnpjStatus.INVALID,
        is_digit_length_valid=True,
        is_check_digits_valid=is_check_digits_valid,
    )


def parse_competence_header_to_iso(value: str) -> str:
    match = BLOCK_COMPETENCE_RE.fullmatch(normalize_dominio_text(value))
    if match is None:
        raise ValueError(f"Invalid payroll competence header: {value!r}")
    return f"{int(match.group('year')):04d}-{int(match.group('month')):02d}"


def parse_brazilian_date_to_iso(value: str) -> str:
    match = DATE_RE.fullmatch(normalize_dominio_text(value))
    if match is None:
        raise ValueError(f"Invalid Brazilian date: {value!r}")
    parsed = date(
        year=int(match.group("year")),
        month=int(match.group("month")),
        day=int(match.group("day")),
    )
    return parsed.isoformat()


def _validate_cnpj_check_digits(value: str) -> bool:
    if len(value) != 14 or not value.isdigit():
        return False
    if value == value[0] * 14:
        return False
    first = _calculate_cnpj_digit(value[:12], weights=(5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _calculate_cnpj_digit(value[:12] + str(first), weights=(6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return value.endswith(f"{first}{second}")


def _calculate_cnpj_digit(value: str, *, weights: tuple[int, ...]) -> int:
    total = sum(int(digit) * weight for digit, weight in zip(value, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder
