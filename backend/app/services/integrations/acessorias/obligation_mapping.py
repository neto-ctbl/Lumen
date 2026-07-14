from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import unicodedata

from backend.app.models.fiscal_obligation import FiscalObligation


MAPPED = "MAPPED"
UNMAPPED = "UNMAPPED"
AMBIGUOUS = "AMBIGUOUS"

SAFE_OBLIGATION_ALIASES: dict[str, str] = {
    "DAS": "DAS",
    "DIFAL": "DIFAL",
    "ICMS": "ICMS",
    "ISS": "ISS",
    "PIS": "PIS",
    "COFINS": "COFINS",
    "PROTEGE": "PROTEGE",
    "DCTFWEB": "DCTFWEB",
    "REINF": "REINF",
    "EFD REINF": "REINF",
    "EFD-REINF": "REINF",
    "EFD CONTRIBUICOES": "EFD_CONTRIBUICOES",
    "EFD CONTRIBUIÇÕES": "EFD_CONTRIBUICOES",
    "DEFIS": "DEFIS",
    "DASN-SIMEI": "DASN_SIMEI",
    "DASN SIMEI": "DASN_SIMEI",
    "PARCELAMENTO": "PARCELAMENTO",
}


@dataclass(slots=True)
class ObligationMatch:
    obligation_id: int | None
    obligation_code: str | None
    mapping_status: str


def normalize_obligation_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    normalized = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    ).upper()
    return " ".join(normalized.replace("_", " ").replace("/", " ").split())


def map_obligation_name(
    name: str | None,
    obligations: Iterable[FiscalObligation],
) -> ObligationMatch:
    normalized = normalize_obligation_name(name)
    if normalized is None:
        return ObligationMatch(obligation_id=None, obligation_code=None, mapping_status=UNMAPPED)

    obligation_list = list(obligations)
    by_code = {
        normalize_obligation_name(obligation.code): obligation
        for obligation in obligation_list
        if normalize_obligation_name(obligation.code) is not None
    }
    exact = by_code.get(normalized)
    if exact is not None:
        return ObligationMatch(obligation_id=exact.id, obligation_code=exact.code, mapping_status=MAPPED)

    alias_code = SAFE_OBLIGATION_ALIASES.get(normalized)
    if alias_code is None:
        return ObligationMatch(obligation_id=None, obligation_code=None, mapping_status=UNMAPPED)

    matched = [obligation for obligation in obligation_list if obligation.code == alias_code]
    if len(matched) == 1:
        return ObligationMatch(obligation_id=matched[0].id, obligation_code=matched[0].code, mapping_status=MAPPED)
    if len(matched) > 1:
        return ObligationMatch(obligation_id=None, obligation_code=alias_code, mapping_status=AMBIGUOUS)
    return ObligationMatch(obligation_id=None, obligation_code=alias_code, mapping_status=UNMAPPED)


def map_external_department(name: str | None, default_department: str) -> str:
    normalized = normalize_obligation_name(name)
    if normalized in {"FISCAL"}:
        return "FISCAL"
    if normalized in {"DEPARTAMENTO PESSOAL", "PESSOAL", "DP"}:
        return "DP"
    return default_department
