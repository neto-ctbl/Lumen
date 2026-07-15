from __future__ import annotations

from typing import Any

from backend.app.schemas.sittax import SittaxCompanyItem, SittaxOfficeReference
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj

from .errors import SittaxBusinessError, SittaxResponseError


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stringify_required(payload: dict[str, Any], field: str) -> str:
    value = _normalize_text(payload.get(field))
    if value is None:
        raise SittaxResponseError(f"Sittax payload is missing required field '{field}'.")
    return value


def _normalize_state_registration(value: Any) -> str | None:
    text = _normalize_text(value)
    return text or None


def _company_status_from_payload(payload: dict[str, Any]) -> str | None:
    homologated = payload.get("homologada")
    if homologated is True:
        return "HOMOLOGADA"
    if homologated is False:
        return "NAO_HOMOLOGADA"
    return None


def map_login_response(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax login response format.")

    code = payload.get("codigo")
    if code not in {0, "0"}:
        raise SittaxBusinessError(f"Sittax login rejected with business code {code!r}.")

    token = _normalize_text(payload.get("token"))
    usuario = payload.get("usuario")
    if token is None or not isinstance(usuario, dict):
        raise SittaxResponseError("Sittax login response is missing token or usuario.")

    escritorio = usuario.get("escritorio")
    if not isinstance(escritorio, dict):
        raise SittaxResponseError("Sittax login response is missing escritorio.")

    office = SittaxOfficeReference(
        id=_stringify_required(escritorio, "id"),
        name=_normalize_text(escritorio.get("nome")),
    )
    return {
        "token": token,
        "office": office,
        "user_id": _normalize_text(usuario.get("id")),
        "user_role": _normalize_text(usuario.get("role") or usuario.get("nivel")),
    }


def map_companies_response(payload: dict[str, Any]) -> list[SittaxCompanyItem]:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax companies response format.")
    if payload.get("sucesso") is not True:
        raise SittaxBusinessError("Sittax companies response returned sucesso=false.")

    companies = payload.get("empresas")
    if not isinstance(companies, list):
        raise SittaxResponseError("Sittax companies response is missing empresas list.")

    items: list[SittaxCompanyItem] = []
    for entry in companies:
        if not isinstance(entry, dict):
            raise SittaxResponseError("Sittax companies payload contains a non-object company entry.")
        items.append(map_company_item(entry))
    return items


def map_company_item(payload: dict[str, Any]) -> SittaxCompanyItem:
    cnpj = normalize_cnpj(payload.get("cnpj"))
    if cnpj is None or len(cnpj) != 14 or not cnpj.isdigit():
        raise SittaxResponseError("Sittax company payload contains an invalid cnpj.")

    return SittaxCompanyItem(
        external_id=_stringify_required(payload, "id"),
        cnpj=cnpj,
        legal_name=_stringify_required(payload, "nome"),
        trade_name=_normalize_text(payload.get("fantasia")),
        state_registration=_normalize_state_registration(payload.get("inscricaoEstadual")),
        state=_normalize_text(payload.get("uf")),
        status=_company_status_from_payload(payload),
        homologated=payload.get("homologada") if isinstance(payload.get("homologada"), bool) else None,
        cash_regime=payload.get("usaRegimeDeCaixa") if isinstance(payload.get("usaRegimeDeCaixa"), bool) else None,
        raw_payload=payload,
    )
