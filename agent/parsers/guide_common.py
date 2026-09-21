"""Small text-layer, currency and taxpayer primitives shared by guide layouts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from pypdf import PdfReader
from unidecode import unidecode

from agent.parsers.contracts import ExtractionStatus

MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")
DATE_RE = re.compile(r"(?<!\d)(?P<day>0[1-9]|[12]\d|3[01])/(?P<month>0[1-9]|1[0-2])/(?P<year>\d{4})(?!\d)")
CNPJ_RE = re.compile(r"(?<!\d)(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)")
CPF_RE = re.compile(r"(?<!\d)(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?!\d)")


@dataclass(frozen=True, slots=True)
class PdfPages:
    status: ExtractionStatus
    pages: tuple[str, ...] = ()


def read_pdf_pages(path: Path) -> PdfPages:
    try:
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return PdfPages(ExtractionStatus.INVALID)
        reader = PdfReader(str(path))
        if reader.is_encrypted or not reader.pages:
            return PdfPages(ExtractionStatus.INVALID)
        pages = tuple(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
    except Exception:
        return PdfPages(ExtractionStatus.INVALID)
    return PdfPages(
        ExtractionStatus.MATCHED if any(page.strip() for page in pages) else ExtractionStatus.INCONCLUSIVE,
        pages,
    )


def search_text(value: str) -> str:
    return " ".join(unidecode(value).upper().split())


def parse_money(value: str) -> Decimal:
    return Decimal(value.replace(".", "").replace(",", "."))


def digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def valid_cnpj(value: str) -> bool:
    if len(value) != 14 or not value.isdigit() or value == value[0] * 14:
        return False
    first = _check_digit(value[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _check_digit(value[:12] + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return value.endswith(f"{first}{second}")


def valid_cpf(value: str) -> bool:
    if len(value) != 11 or not value.isdigit() or value == value[0] * 11:
        return False
    first = _check_digit(value[:9], tuple(range(10, 1, -1)))
    second = _check_digit(value[:9] + str(first), tuple(range(11, 1, -1)))
    return value.endswith(f"{first}{second}")


def _check_digit(value: str, weights: tuple[int, ...]) -> int:
    remainder = sum(int(digit) * weight for digit, weight in zip(value, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def parse_date(value: str) -> str | None:
    match = DATE_RE.fullmatch(value.strip())
    if match is None:
        return None
    try:
        return date(int(match["year"]), int(match["month"]), int(match["day"])).isoformat()
    except ValueError:
        return None
