"""Conservative filename-only classifier hints; this is not a fiscal parser."""

from __future__ import annotations

import re

from unidecode import unidecode


_KEYWORDS = (
    "DAS", "PIS", "COFINS", "ICMS", "ISS", "DIFAL", "PROTEGE", "PGFN", "SISPAR", "PARC",
    "DCTFWEB", "DARF", "REINF", "MIT", "IRPJ", "CSLL",
)


def classify_file_name(file_name: str) -> str:
    normalized = re.sub(r"[_.()\-]+", " ", unidecode(file_name).upper())
    tokens = set(re.findall(r"[A-Z0-9]+", normalized))
    matches = {keyword for keyword in _KEYWORDS if keyword in tokens}
    if {"PGFN", "SISPAR"}.issubset(matches):
        matches.difference_update({"PGFN", "SISPAR", "PARC"})
        matches.add("PGFN_SISPAR")
    if not matches:
        return "UNKNOWN"
    if len(matches) != 1:
        return "AMBIGUOUS"
    return matches.pop()
