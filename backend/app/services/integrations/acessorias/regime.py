from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import FISCAL_REGIME_LABELS, FiscalRegime
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.fiscal_alert import FiscalAlert


REGIME_DIVERGENCE_CODE = "REGIME_DIVERGENCE_ACESSORIAS_ECONTROLE"
MAPPED = "MAPPED"
UNMAPPED = "UNMAPPED"
MISSING = "MISSING"

REGIME_CODE_MAP: dict[int, FiscalRegime] = {
    1: FiscalRegime.SIMPLES_NACIONAL,
    2: FiscalRegime.SIMPLES_NACIONAL,
    3: FiscalRegime.LUCRO_PRESUMIDO,
    4: FiscalRegime.LUCRO_PRESUMIDO,
    5: FiscalRegime.LUCRO_REAL,
    6: FiscalRegime.MEI,
    10: FiscalRegime.IMUNE_ISENTA,
}

REGIME_LABEL_ALIASES: dict[str, FiscalRegime] = {
    "SIMPLES NACIONAL": FiscalRegime.SIMPLES_NACIONAL,
    "SIMPLES NACIONAL COM INSCRICAO ESTADUAL": FiscalRegime.SIMPLES_NACIONAL,
    "SIMPLES NACIONAL SEM INSCRICAO ESTADUAL": FiscalRegime.SIMPLES_NACIONAL,
    "LUCRO PRESUMIDO": FiscalRegime.LUCRO_PRESUMIDO,
    "LUCRO PRESUMIDO COM INSCRICAO ESTADUAL - INDUSTRIA/COMERCIO": FiscalRegime.LUCRO_PRESUMIDO,
    "LUCRO PRESUMIDO SEM INSCRICAO ESTADUAL - SERVICO": FiscalRegime.LUCRO_PRESUMIDO,
    "LUCRO REAL": FiscalRegime.LUCRO_REAL,
    "MEI": FiscalRegime.MEI,
    "MEI - MICRO EMPREENDEDOR INDIVIDUAL": FiscalRegime.MEI,
    "IMUNE/ISENTA": FiscalRegime.IMUNE_ISENTA,
    "IMUNE ISENTA": FiscalRegime.IMUNE_ISENTA,
}


@dataclass(slots=True)
class RegimeResolution:
    raw: str | None
    code: int | None
    canonical: str | None
    mapping_status: str


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    ).upper()


def resolve_acessorias_regime(value: Any) -> RegimeResolution:
    raw = None if value is None else str(value).strip() or None
    if raw is None:
        return RegimeResolution(raw=None, code=None, canonical=None, mapping_status=MISSING)

    code: int | None = None
    if isinstance(value, int):
        code = value
    else:
        text_digits = str(value).strip()
        if text_digits.isdigit():
            code = int(text_digits)

    if code is not None:
        canonical = REGIME_CODE_MAP.get(code)
        return RegimeResolution(
            raw=raw,
            code=code,
            canonical=canonical.value if canonical else None,
            mapping_status=MAPPED if canonical else UNMAPPED,
        )

    normalized = normalize_text(raw)
    canonical = REGIME_LABEL_ALIASES.get(normalized or "")
    return RegimeResolution(
        raw=raw,
        code=None,
        canonical=canonical.value if canonical else None,
        mapping_status=MAPPED if canonical else UNMAPPED,
    )


def resolve_econtrole_regime(raw_payload: dict[str, Any] | None) -> RegimeResolution:
    if not raw_payload:
        return RegimeResolution(raw=None, code=None, canonical=None, mapping_status=MISSING)

    for key in ("regime", "regime_tributario", "regimeTributario", "tax_regime", "taxRegime"):
        if key in raw_payload:
            return resolve_acessorias_regime(raw_payload.get(key))
    return RegimeResolution(raw=None, code=None, canonical=None, mapping_status=MISSING)


def regime_label_from_canonical(canonical: str | None) -> str | None:
    if canonical is None:
        return None
    try:
        return FISCAL_REGIME_LABELS[FiscalRegime(canonical)]
    except Exception:
        return canonical


def upsert_regime_divergence_alert(
    session: Session,
    *,
    organization_id: int,
    company_id: int,
    acessorias_snapshot: AcessoriasCompanySnapshot,
    econtrole_raw_payload: dict[str, Any] | None,
) -> FiscalAlert | None:
    acessorias_regime = resolve_acessorias_regime(acessorias_snapshot.regime_raw or acessorias_snapshot.regime_code)
    econtrole_regime = resolve_econtrole_regime(econtrole_raw_payload)

    if acessorias_regime.mapping_status != MAPPED or econtrole_regime.mapping_status != MAPPED:
        return None
    if acessorias_regime.canonical == econtrole_regime.canonical:
        return None

    alert = session.scalar(
        select(FiscalAlert).where(
            FiscalAlert.organization_id == organization_id,
            FiscalAlert.company_id == company_id,
            FiscalAlert.code == REGIME_DIVERGENCE_CODE,
        )
    )
    message = (
        f"Regime oficial Acessorias diverge do eControle: "
        f"{regime_label_from_canonical(acessorias_regime.canonical)} vs "
        f"{regime_label_from_canonical(econtrole_regime.canonical)}."
    )
    details = {
        "acessorias_regime_raw": acessorias_regime.raw,
        "acessorias_regime_canonical": acessorias_regime.canonical,
        "econtrole_regime_raw": econtrole_regime.raw,
        "econtrole_regime_canonical": econtrole_regime.canonical,
    }
    if alert is None:
        alert = FiscalAlert(
            organization_id=organization_id,
            company_id=company_id,
            period_id=None,
            obligation_status_id=None,
            code=REGIME_DIVERGENCE_CODE,
            title="Divergencia de regime tributario",
            message=message,
            severity="MEDIUM",
            department="FISCAL",
            source="ACESSORIAS_API",
            status="OPEN",
            details=details,
        )
        session.add(alert)
    else:
        alert.message = message
        alert.source = "ACESSORIAS_API"
        alert.status = "OPEN"
        alert.details = details
    session.flush()
    return alert
