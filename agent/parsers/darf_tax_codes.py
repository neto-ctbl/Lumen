"""Empirical code mapping for layouts validated in S11.1-B, not a fiscal catalog."""

import re

from agent.parsers.guide_common import search_text

# Base codes actually observed in the supplied SENDA/Sicalc corpus.
REVENUE_TAX_CODES = {
    "8109": "PIS",
    "2172": "COFINS",
    "2089": "IRPJ",
    "5993": "IRPJ",
    "2372": "CSLL",
    "2484": "CSLL",
}
TAX_DESCRIPTION_MARKERS = ("COFINS", "CSLL", "IRPJ", "PIS", "INSS", "IRRF")


def identify_tax(code: str, description: str) -> tuple[str, str | None, str | None]:
    by_code = REVENUE_TAX_CODES.get(code.split("-", maxsplit=1)[0])
    tokens = {tax for tax in TAX_DESCRIPTION_MARKERS if re.search(rf"\b{tax}\b", search_text(description))}
    by_description = next(iter(tokens)) if len(tokens) == 1 else None
    if by_code:
        warning = "DARF_TAX_CODE_DESCRIPTION_CONFLICT" if tokens and tokens != {by_code} else None
        return by_code, "REVENUE_CODE", warning
    if by_description:
        return by_description, "DESCRIPTION", "DARF_REVENUE_CODE_UNKNOWN"
    return "UNKNOWN", None, "DARF_REVENUE_CODE_UNKNOWN"
