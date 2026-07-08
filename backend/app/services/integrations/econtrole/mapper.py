from __future__ import annotations

from datetime import datetime
from typing import Any


class EControleMappingError(ValueError):
    pass


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "econtrole_company_id": ("id",),
    "econtrole_profile_id": ("profile_id", "profileId"),
    "cnpj": ("cnpj",),
    "razao_social": ("razao_social", "razaoSocial"),
    "nome_fantasia": ("nome_fantasia", "nomeFantasia"),
    "apelido_pasta": ("apelido_pasta", "apelidoPasta"),
    "situacao": ("situacao",),
    "inscricao_estadual": ("inscricao_estadual", "inscricaoEstadual"),
    "inscricao_municipal": ("inscricao_municipal", "inscricaoMunicipal"),
    "municipio": ("municipio",),
    "uf": ("uf",),
    "cnae_principal": ("cnae_principal", "cnaePrincipal"),
    "cnaes_secundarios": ("cnaes_secundarios", "cnaesSecundarios"),
    "updated_at_econtrole": ("updated_at", "updatedAt"),
}


def map_econtrole_company_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cnpj_raw = _pick(payload, "cnpj")
    razao_social_raw = _pick(payload, "razao_social")

    cnpj = normalize_cnpj(cnpj_raw)
    razao_social = _normalize_text(razao_social_raw)
    if not cnpj:
        raise EControleMappingError("Field 'cnpj' is required.")
    if not razao_social:
        raise EControleMappingError("Field 'razao_social' is required.")

    cnaes_secundarios = _pick(payload, "cnaes_secundarios")
    if cnaes_secundarios is not None and not isinstance(cnaes_secundarios, list):
        raise EControleMappingError("Field 'cnaes_secundarios' must be a list when provided.")

    return {
        "econtrole_company_id": _stringify(_pick(payload, "econtrole_company_id")),
        "econtrole_profile_id": _stringify(_pick(payload, "econtrole_profile_id")),
        "cnpj": cnpj,
        "razao_social": razao_social,
        "nome_fantasia": _normalize_text(_pick(payload, "nome_fantasia")),
        "apelido_pasta": _normalize_text(_pick(payload, "apelido_pasta")),
        "situacao": _normalize_text(_pick(payload, "situacao")),
        "inscricao_estadual": _normalize_ie(_pick(payload, "inscricao_estadual")),
        "inscricao_municipal": _normalize_text(_pick(payload, "inscricao_municipal")),
        "municipio": _normalize_text(_pick(payload, "municipio")),
        "uf": _normalize_uf(_pick(payload, "uf")),
        "cnae_principal": _normalize_text(_pick(payload, "cnae_principal")),
        "cnaes_secundarios": [_stringify(item).strip() for item in cnaes_secundarios] if cnaes_secundarios else None,
        "updated_at_econtrole": _parse_datetime(_pick(payload, "updated_at_econtrole")),
        "raw_econtrole": payload,
    }


def normalize_cnpj(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 14:
        return digits
    return text[:18]


def _pick(payload: dict[str, Any], field: str) -> Any:
    for alias in FIELD_ALIASES[field]:
        if alias in payload:
            return payload[alias]
    return None


def _normalize_ie(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if text.upper() == "ISENTO":
        return text
    return text


def _normalize_uf(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return text.upper()[:2]


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_datetime(value: Any) -> datetime | None:
    text = _normalize_text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise EControleMappingError("Field 'updated_at' has invalid datetime format.") from exc
