"""Empirical Goiás codes from the inspected DARE corpus, not a tax-law catalog."""

from __future__ import annotations

from agent.parsers.guide_common import search_text

STATE_REVENUE_CODES = {
    "108": ("ICMS", "ICMS"),
    "4502": ("ICMS", "DIFAL"),
    "159": ("ICMS", "DIFAL_CONSUMPTION_ASSET"),
    "4014": ("STATE_REVENUE", "PROTEGE"),
}

# The PROTEGE body has a subordinate "CONTRIBUICAO" code. That generic
# qualifier is known only under its explicit parent, never standalone.
STATE_REVENUE_SUBTYPES = {("4014", "41"): ("STATE_REVENUE", "PROTEGE")}


def is_known_state_code(code: str, parent_code: str | None = None) -> bool:
    return code in STATE_REVENUE_CODES or (parent_code, code) in STATE_REVENUE_SUBTYPES


def classify_state_revenue(code: str, description: str, parent_code: str | None = None,
                           parent_description: str | None = None) -> tuple[str, str, str | None, tuple[str, ...]]:
    text = search_text(description)
    parent = search_text(parent_description or "")
    candidates = set()
    if "PROTEGE" in text:
        candidates.add(("STATE_REVENUE", "PROTEGE"))
    if "DIFAL" in text or "DIFERENCIAL DE ALIQUOT" in text:
        kind = "DIFAL_CONSUMPTION_ASSET" if any(term in text for term in ("CONSUMO", "ATIVO IMOBILIZADO")) else "DIFAL"
        candidates.add(("ICMS", kind))
    if "ICMS" in text and "NORMAL" in text:
        candidates.add(("ICMS", "ICMS"))
    known = STATE_REVENUE_SUBTYPES.get((parent_code, code)) or STATE_REVENUE_CODES.get(code)
    warnings = [] if known else ["STATE_REVENUE_CODE_UNKNOWN"]
    # 108 means NORMAL only in its inspected ICMS parent context.
    if code == "108" and not (parent_code == "1" and "ICMS" in parent or "ICMS" in text):
        known = None
    if len(candidates) > 1 or known and candidates and known not in candidates:
        return "UNKNOWN", "UNKNOWN", None, (*warnings, "STATE_REVENUE_CLASSIFICATION_CONFLICT")
    if known:
        source = "PARENT_AND_REVENUE_CODE" if (parent_code, code) in STATE_REVENUE_SUBTYPES else "REVENUE_CODE"
        return *known, source, tuple(warnings)
    if len(candidates) == 1:
        tax, kind = candidates.pop()
        return tax, kind, "DESCRIPTION", (*warnings, "STATE_REVENUE_CLASSIFIED_FROM_DESCRIPTION")
    return "UNKNOWN", "UNKNOWN", None, (*warnings, "STATE_GUIDE_KIND_INCONCLUSIVE")
