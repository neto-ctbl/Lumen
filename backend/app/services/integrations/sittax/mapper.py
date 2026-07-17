from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from backend.app.core.security import mask_value
from backend.app.schemas.sittax import SittaxApuracaoItem, SittaxCompanyItem, SittaxOfficeReference
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj

from .errors import SittaxBusinessError, SittaxContextMismatchError, SittaxResponseError


SUCCESS_LOGIN_CODES = {0, 200, "0", "200"}
DECIMAL_2_PLACES = Decimal("0.01")


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise SittaxResponseError("Sittax payload contains invalid numeric boolean value.")
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return Decimal(normalized).quantize(DECIMAL_2_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise SittaxResponseError("Sittax payload contains invalid numeric value.") from exc


def _normalize_period_reference(value: Any) -> str | None:
    if isinstance(value, dict):
        for field in ("dataInicial", "dataFinal"):
            candidate = _normalize_text(value.get(field))
            if candidate:
                return _normalize_period_reference(candidate[:10])
        raise SittaxResponseError("Sittax payload contains invalid periodoFiscal.")
    text = _normalize_text(value)
    if text is None:
        return None
    if len(text) >= 7 and text[4] == "-" and text[5:7].isdigit():
        year = text[:4]
        month = text[5:7]
        month_number = int(month)
        if month_number < 1 or month_number > 12:
            raise SittaxResponseError("Sittax payload contains invalid periodoFiscal.")
        return f"{year}-{month_number:02d}"
    parts = text.split("/")
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 4:
        raise SittaxResponseError("Sittax payload contains invalid periodoFiscal.")
    month, year = parts
    if not month.isdigit() or not year.isdigit():
        raise SittaxResponseError("Sittax payload contains invalid periodoFiscal.")
    month_number = int(month)
    if month_number < 1 or month_number > 12:
        raise SittaxResponseError("Sittax payload contains invalid periodoFiscal.")
    return f"{year}-{month_number:02d}"


def _normalize_json_list(value: Any) -> list[dict[str, Any] | str]:
    if value is None:
        return []
    if value is False:
        return []
    if not isinstance(value, list):
        raise SittaxResponseError("Sittax payload contains an invalid list block.")
    return [item for item in value if isinstance(item, (dict, str))]


def _normalize_json_object_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SittaxResponseError("Sittax payload contains an invalid object list block.")
    return [item for item in value if isinstance(item, dict)]


def _normalize_optional_bool(payload: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _normalize_datetime_text(value: Any) -> str | None:
    text = _normalize_text(value)
    return text or None


def _resolve_company_context(data: dict[str, Any], *, requested_company_cnpj: str) -> tuple[str | None, dict[str, Any] | None]:
    confirmed_company_cnpj = normalize_cnpj(data.get("empresaCnpj"))
    companies = _normalize_json_object_list(data.get("empresasApuracao") or data.get("empresasDaApuracao"))
    matched_company: dict[str, Any] | None = None
    if confirmed_company_cnpj is None:
        for company in companies:
            company_cnpj = normalize_cnpj(company.get("cnpj"))
            if company_cnpj == requested_company_cnpj:
                confirmed_company_cnpj = company_cnpj
                matched_company = company
                break
    if matched_company is None:
        for company in companies:
            company_cnpj = normalize_cnpj(company.get("cnpj"))
            if company_cnpj == confirmed_company_cnpj:
                matched_company = company
                break
    if confirmed_company_cnpj is None:
        company_cnpjs = [normalize_cnpj(company.get("cnpj")) for company in companies]
        valid_company_cnpjs = [cnpj for cnpj in company_cnpjs if cnpj is not None]
        if len(valid_company_cnpjs) == 1:
            confirmed_company_cnpj = valid_company_cnpjs[0]
        elif valid_company_cnpjs:
            confirmed_company_cnpj = valid_company_cnpjs[0]
    return confirmed_company_cnpj, matched_company


def _normalize_cfops(company_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if company_payload is None:
        return []
    blocks: list[dict[str, Any]] = []
    for key in ("resumoPorCfop", "resumoPorCfopSittax", "resumoPorCfopXml"):
        value = company_payload.get(key)
        if isinstance(value, list):
            blocks.extend(item for item in value if isinstance(item, dict))
    return blocks


def _normalize_activities(company_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if company_payload is None:
        return []
    activities = company_payload.get("atividades")
    if not isinstance(activities, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in activities:
        text = _normalize_text(item)
        if text is not None:
            normalized.append({"code": text})
    return normalized


def _normalize_payrolls(data: dict[str, Any], company_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for key in ("folhas", "folhasDePagamento"):
        value = data.get(key)
        if isinstance(value, list):
            blocks.extend(item for item in value if isinstance(item, dict))
    if blocks:
        return blocks
    if company_payload is not None and isinstance(company_payload.get("empresaTemFolha"), bool):
        return [{"empresaTemFolha": company_payload["empresaTemFolha"]}]
    if isinstance(data.get("folhaDePagamentos"), bool):
        return [{"folhaDePagamentos": data["folhaDePagamentos"]}]
    return []


def _stringify_required(payload: dict[str, Any], field: str) -> str:
    value = _normalize_text(payload.get(field))
    if value is None:
        raise SittaxResponseError(f"Sittax payload is missing required field '{field}'.")
    return value


def _resolve_apuracao_id(
    data: dict[str, Any],
    *,
    requested_company_cnpj: str,
    requested_period: str,
) -> str:
    explicit_id = _normalize_text(data.get("id"))
    if explicit_id is not None:
        return explicit_id
    return f"apuracao:{requested_company_cnpj}:{requested_period}"


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
    if code not in SUCCESS_LOGIN_CODES:
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


def map_apuracao_response(
    payload: dict[str, Any],
    *,
    requested_company_cnpj: str,
    requested_period: str,
) -> SittaxApuracaoItem:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax apuracao response format.")
    if payload.get("ok") is not True:
        raise SittaxBusinessError(f"Sittax apuracao rejected with status {payload.get('status')!r}.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SittaxResponseError("Sittax apuracao response is missing data object.")

    confirmed_company_cnpj, company_payload = _resolve_company_context(
        data,
        requested_company_cnpj=requested_company_cnpj,
    )
    if confirmed_company_cnpj is not None and confirmed_company_cnpj != requested_company_cnpj:
        raise SittaxContextMismatchError(
            "Sittax apuracao returned mismatched company context: "
            f"requested_company={mask_value(requested_company_cnpj)} "
            f"returned_company={mask_value(confirmed_company_cnpj)}"
        )

    confirmed_period = _normalize_period_reference(data.get("periodoFiscal"))
    if confirmed_period != requested_period:
        raise SittaxContextMismatchError(
            "Sittax apuracao returned mismatched period context: "
            f"requested_period={requested_period} returned_period={confirmed_period}"
        )

    risks_payload = data.get("relatorioDeConferenciaSittax")
    risks: list[dict[str, Any] | str]
    if risks_payload is None:
        risks = []
    elif isinstance(risks_payload, list):
        risks = [item for item in risks_payload if isinstance(item, (dict, str))]
    elif isinstance(risks_payload, dict):
        risks = [risks_payload]
    else:
        raise SittaxResponseError("Sittax apuracao risks block has invalid format.")

    return SittaxApuracaoItem(
        requested_company_cnpj=requested_company_cnpj,
        requested_period=requested_period,
        confirmed_company_cnpj=confirmed_company_cnpj,
        confirmed_period=confirmed_period,
        apuracao_id=_resolve_apuracao_id(
            data,
            requested_company_cnpj=requested_company_cnpj,
            requested_period=requested_period,
        ),
        office_name=_normalize_text(data.get("escritorioNome")),
        company_name=_normalize_text(data.get("empresaNome")) or _normalize_text((company_payload or {}).get("nome")),
        is_transmitted=(
            True
            if _normalize_datetime_text(data.get("dataHoraTransmissao")) is not None
            else False if _normalize_text(data.get("tipoDaTransmissao")) == "NAO_TRANSMITIDA" else None
        ),
        transmission_in_progress=data.get("emTransmissao") if isinstance(data.get("emTransmissao"), bool) else None,
        das_number=_normalize_text(data.get("numeroDas")),
        declaration_number=_normalize_text(data.get("numeroDeclaracao")),
        statement_number=_normalize_text(data.get("numeroExtrato")),
        transmission_type=_normalize_text(data.get("tipoDaTransmissao")),
        transmitted_at=_normalize_datetime_text(data.get("dataHoraTransmissao")),
        net_revenue=_normalize_decimal(data.get("receitaLiquida")),
        product_revenue=_normalize_decimal(data.get("receitaProdutos")),
        service_revenue=_normalize_decimal(data.get("receitaServicos")),
        return_revenue=_normalize_decimal(data.get("receitaDevolucao")),
        rbt12=_normalize_decimal(data.get("rbt12")),
        rba=_normalize_decimal(data.get("rba")),
        das_amount=_normalize_decimal(data.get("valorDas")),
        das_xml_amount=_normalize_decimal(data.get("valorDasXml")),
        factor_r_percent=_normalize_decimal(data.get("percentualFatorR")),
        company_has_payroll=(
            data.get("folhaDePagamentos")
            if isinstance(data.get("folhaDePagamentos"), bool)
            else company_payload.get("empresaTemFolha")
            if company_payload is not None and isinstance(company_payload.get("empresaTemFolha"), bool)
            else None
        ),
        taxes_icms=_normalize_optional_bool(
            company_payload or data,
            "empresaTributaIcms",
            "tributaIcms",
            "tributaICMS",
        ),
        taxes_iss=_normalize_optional_bool(
            company_payload or data,
            "empresaTributaIss",
            "tributaIss",
            "tributaISS",
        ),
        taxes_ipi=_normalize_optional_bool(
            company_payload or data,
            "empresaTributaIpi",
            "tributaIpi",
            "tributaIPI",
        ),
        taxes_pis_cofins=_normalize_optional_bool(
            company_payload or data,
            "empresaTributaPisCofins",
            "tributaPisCofins",
            "tributaPISCOFINS",
        ),
        companies_apuracao=_normalize_json_object_list(
            data.get("empresasApuracao") or data.get("empresasDaApuracao")
        ),
        annexes=_normalize_json_object_list(data.get("resumosTributacaoSittax")),
        cfops=_normalize_cfops(company_payload),
        activities=_normalize_activities(company_payload),
        payrolls=_normalize_payrolls(data, company_payload),
        alerts=_normalize_json_list(data.get("mensagens")),
        errors=_normalize_json_list(data.get("inconsistencias")),
        risks=risks,
        raw_payload=data,
    )
