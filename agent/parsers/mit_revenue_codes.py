"""Versioned, non-authoritative reference catalog for MIT revenue codes.

The catalog is metadata extracted from the official MIT 1.0 manual table.  It
helps interpret an observed code, but never decides whether a document is MIT
and never rejects a document merely because Receita introduced a new code.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

MIT_REVENUE_CATALOG_VERSION = "RFB_MIT_MANUAL_1_0_2025_01"
MIT_REVENUE_CATALOG_EXPECTED_COUNT = 240


@dataclass(frozen=True, slots=True)
class MitRevenueCode:
    code: str
    display_code: str
    group: str
    periodicity: str
    description: str | None = None


_GROUP_TAX = {
    "IRPJ": "IRPJ",
    "CSLL": "CSLL",
    "IRRF": "IRRF",
    "IPI": "IPI",
    "IOF": "IOF",
    "PIS/PASEP": "PIS",
    "COFINS": "COFINS",
    "Cont. Diversas": "CONTRIBUICOES_DIVERSAS",
    "CPSS": "CPSS",
    "RET": "RET_PAGAMENTO_UNIFICADO",
}

# Compact source representation keeps review easy while retaining every entry
# from the official table. Descriptions are intentionally not copied: the
# source PDF's embedded text corrupts accents, while code/group/periodicity are
# machine-verifiable and sufficient for conservative enrichment.
_CODES_BY_GROUP_AND_PERIODICITY = {
    ("IRPJ", "TR"): "0220-01 0220-08 0220-10 0220-12 1599-01 1599-10 2089-01 2089-02 2089-08 2089-09 2089-10 2089-12 3373-01 3373-08 3373-10 3373-12 5625-01 5625-02 5625-08 5625-09 5625-10 5625-12 7756-01 7756-04 7756-05",
    ("IRPJ", "ME"): "0231-01 0507-01 2319-01 2362-01 2362-02 2362-08 2362-09 2362-12 3225-01 3317-01 5993-01 5993-02 5993-08 5993-09 5993-12 7756-02 9086-01",
    ("IRPJ", "AN"): "2390-01 2390-10 2430-01 2430-08 2430-10 2456-01 2456-08 2456-10 7756-03",
    ("CSLL", "TR"): "2030-01 2030-10 2372-01 2372-03 2372-08 2372-10 2372-12 6012-01 6012-08 6012-10 6012-12 7837-01 7837-04",
    ("CSLL", "ME"): "2469-01 2484-01 2484-08 2484-12 7837-02",
    ("CSLL", "AN"): "6758-01 6758-10 6773-01 6773-08 6773-10 7837-03",
    ("IRRF", "ME"): "7769-01 7769-02 7769-03",
    ("IPI", "ME"): "0668-03 0676-02 0676-16 0821-02 0838-02 1020-05 1020-06 1097-05 1097-16 2401-02 2410-03 2410-04 5110-01 5123-01 5123-16",
    ("IOF", "ME"): "1150-02 1150-05 2927-02 2927-10 7893-02 7893-05",
    ("IOF", "DC"): "1150-03 1150-04 3467-02 4028-02 4290-02 5220-02 6854-02 6895-02 7893-03 7893-04",
    ("PIS/PASEP", "ME"): "0679-03 0679-04 0691-03 0691-04 0906-01 0906-02 1921-01 1921-02 1921-03 1921-04 3703-01 4574-01 6824-01 6824-08 6912-01 6912-08 6912-16 6912-17 7797-01 7797-02 8109-02 8109-07 8109-08 8109-09 8109-16 8109-17 8496-01 8496-08",
    ("PIS/PASEP", "DI"): "3121-02 5434-01 5434-08 5434-10 5434-11 8109-03",
    ("COFINS", "ME"): "0760-03 0760-04 0776-03 0776-04 0929-01 0929-02 1840-01 1840-02 1840-03 1840-04 2172-01 2172-04 2172-08 2172-09 2172-16 2172-17 5856-01 5856-08 5856-16 5856-17 6840-01 6840-08 7784-01 7784-02 7987-01 8645-01 8645-08",
    ("COFINS", "DI"): "2172-02 5442-01 5442-08 5442-10 5442-11",
    ("Cont. Diversas", "DC"): "8536-02",
    ("Cont. Diversas", "ME"): "8741-01 8741-11 9331-01 9331-03 9331-04 9331-05 9331-06 9331-07 9331-08 9331-09 9331-10 9197-01",
    ("Cont. Diversas", "DI"): "9013-01",
    ("CPSS", "DC"): "1661-01 1684-03 1700-01 1717-01 1723-03 1730-03 1752-03 1769-01 1781-04 1814-01 5492-01 5502-01 5519-01",
    ("CPSS", "ME"): "1781-02 1837-04",
    ("RET", "ME"): "1068-01 1068-02 1068-05 1068-06 1068-07 4095-01 4095-02 4112-01 4112-02 4112-03 4112-05 4112-06 4112-07 4112-08 4138-01 4138-02 4138-03 4138-05 4138-06 4138-07 4138-08 4153-01 4153-02 4153-03 4153-05 4153-06 4153-07 4153-08 4166-01 4166-02 4166-03 4166-05 4166-06 4166-07 4166-08 6177-01",
}


def _build_catalog() -> dict[str, MitRevenueCode]:
    catalog: dict[str, MitRevenueCode] = {}
    for (source_group, periodicity), codes in _CODES_BY_GROUP_AND_PERIODICITY.items():
        for display_code in codes.split():
            code = display_code.replace("-", "")
            if code in catalog:
                raise RuntimeError(f"duplicate MIT revenue code: {display_code}")
            catalog[code] = MitRevenueCode(
                code=code,
                display_code=display_code,
                group=_GROUP_TAX[source_group],
                periodicity=periodicity,
            )
    if len(catalog) != MIT_REVENUE_CATALOG_EXPECTED_COUNT:
        raise RuntimeError("incomplete MIT revenue code catalog")
    return catalog


MIT_REVENUE_CODES = _build_catalog()


def normalize_mit_revenue_code(value: str) -> str | None:
    """Return the official six digits, or ``None`` for an invalid shape."""
    normalized = re.sub(r"[.\-/\s]", "", value.strip())
    return normalized if len(normalized) == 6 and normalized.isdigit() else None


def lookup_mit_revenue_code(value: str) -> MitRevenueCode | None:
    normalized = normalize_mit_revenue_code(value)
    return MIT_REVENUE_CODES.get(normalized) if normalized else None
