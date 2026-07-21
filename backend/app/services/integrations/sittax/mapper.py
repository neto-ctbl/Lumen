from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from backend.app.core.security import mask_value
from backend.app.schemas.sittax import (
    SittaxApuracaoItem,
    SittaxCompanyItem,
    SittaxDifalItem,
    SittaxFiscalDocumentItem,
    SittaxFiscalDocumentPage,
    SittaxOfficeReference,
    SittaxTaskItem,
    SittaxTaskPage,
)
from backend.app.services.integrations.econtrole.mapper import normalize_cnpj

from .errors import SittaxBusinessError, SittaxContextMismatchError, SittaxResponseError


SUCCESS_LOGIN_CODES = {0, 200, "0", "200"}
DECIMAL_2_PLACES = Decimal("0.01")
ZERO_DATETIME_PREFIXES = ("0001-01-01", "0000-00-00")


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
    if text is not None and text.startswith(ZERO_DATETIME_PREFIXES):
        return None
    return text or None


def _normalize_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SittaxResponseError("Sittax payload contains invalid integer boolean value.")
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise SittaxResponseError("Sittax payload contains invalid integer value.") from exc


def _normalize_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return _normalize_int(value)
    except SittaxResponseError:
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise SittaxResponseError("Sittax payload contains an invalid string list block.")
    normalized: list[str] = []
    for item in value:
        text = _normalize_text(item)
        if text is not None:
            normalized.append(text)
    return normalized


def _normalize_extension(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if text.startswith("."):
        return text.lower()
    return None


def _hash_key(parts: list[str]) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


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
        cnpj=normalize_cnpj(escritorio.get("cnpj")),
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


def map_difal_response(payload: dict[str, Any]) -> SittaxDifalItem:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax DIFAL response format.")
    if payload.get("sucesso") is not True:
        raise SittaxBusinessError("Sittax DIFAL response returned sucesso=false.")
    difal = payload.get("difal")
    if not isinstance(difal, dict):
        raise SittaxResponseError("Sittax DIFAL response is missing difal object.")

    dare_numbers = [
        dare
        for dare in [
            _normalize_text(difal.get("numeroDareGuiaRevenda")),
            _normalize_text(difal.get("numeroDareGuiaUsoConsumoImobilizado")),
        ]
        if dare is not None
    ]
    inconsistencies = _normalize_json_list(difal.get("creditos"))
    total_amount = sum(
        (
            amount
            for amount in [
                _normalize_decimal(difal.get("valorGuiaRevenda")),
                _normalize_decimal(difal.get("totalGuiaUsoConsumoImobilizado")),
                _normalize_decimal(difal.get("totalGuiaIndustrializacao")),
            ]
            if amount is not None
        ),
        start=Decimal("0.00"),
    )
    return SittaxDifalItem(
        difal_id=_normalize_text(difal.get("id")) or "difal",
        has_guide=difal.get("possuiGuia") if isinstance(difal.get("possuiGuia"), bool) else None,
        dare_numbers=dare_numbers,
        total_amount=total_amount,
        resale_amount=_normalize_decimal(difal.get("valorGuiaRevendaUtilizandoCredito"))
        or _normalize_decimal(difal.get("valorGuiaRevenda")),
        use_consumption_fixed_asset_amount=_normalize_decimal(difal.get("valorGuiaUsoConsumoImobilizadoUtilizandoCredito"))
        or _normalize_decimal(difal.get("totalGuiaUsoConsumoImobilizado")),
        total_purchases=_normalize_decimal(difal.get("totalTodasCompras")),
        closing_date=_normalize_datetime_text(difal.get("dataFechamento")),
        transmission_date=_normalize_datetime_text(difal.get("dataTransmissao")),
        message=_normalize_text(payload.get("mensagem")),
        notes_without_type_or_reference=(
            difal.get("temNotasComReferenciaSemTipo")
            if isinstance(difal.get("temNotasComReferenciaSemTipo"), bool)
            else None
        ),
        inconsistencies=inconsistencies,
        raw_payload=difal,
    )


def map_fiscal_document_page(payload: dict[str, Any], *, direction: str, page_number: int, page_size: int) -> SittaxFiscalDocumentPage:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax fiscal document response format.")
    if payload.get("sucesso") is not True:
        raise SittaxBusinessError("Sittax fiscal document response returned sucesso=false.")
    lista = payload.get("lista")
    if not isinstance(lista, list):
        raise SittaxResponseError("Sittax fiscal document response is missing lista.")

    items = [map_fiscal_document_item(item, direction=direction) for item in lista if isinstance(item, dict)]
    return SittaxFiscalDocumentPage(
        page_number=page_number,
        page_size=page_size,
        total=_normalize_int(payload.get("total")),
        total_filtered=_normalize_int(payload.get("totalFiltrado")),
        items=items,
        raw_payload=payload,
    )


def map_fiscal_document_item(payload: dict[str, Any], *, direction: str) -> SittaxFiscalDocumentItem:
    if direction not in {"ENTRADA", "SAIDA"}:
        raise SittaxResponseError("Sittax fiscal document direction is invalid.")

    sittax_document_id = _normalize_text(payload.get("id"))
    access_key = _normalize_text(payload.get("chave_acesso"))
    document_number = _normalize_text(payload.get("numero"))
    model = _normalize_text(payload.get("modelo"))
    issue_date = _normalize_datetime_text(payload.get("data_emissao"))
    period_reference = _normalize_period_reference(payload.get("data_competencia"))
    cfops = _normalize_string_list(payload.get("cfops"))

    source_document_key = sittax_document_id or access_key
    if source_document_key is None:
        source_document_key = _hash_key(
            [
                direction,
                period_reference,
                document_number or "",
                model or "",
                issue_date or "",
                _normalize_text(payload.get("status")) or "",
                _normalize_text(payload.get("emitente_nome") or payload.get("destinatario_nome")) or "",
            ]
        )

    return SittaxFiscalDocumentItem(
        source_document_key=source_document_key,
        sittax_document_id=sittax_document_id,
        document_direction=direction,
        access_key=access_key,
        model=model,
        document_number=document_number,
        status=_normalize_text(payload.get("status")),
        issue_date=issue_date,
        entry_date=_normalize_datetime_text(payload.get("data_entrada")),
        period_reference=period_reference,
        issuer_name=_normalize_text(payload.get("emitente_nome")),
        issuer_state=_normalize_text(payload.get("emitente_uf")),
        recipient_name=_normalize_text(payload.get("destinatario_nome")),
        recipient_state=_normalize_text(payload.get("destinatario_uf")),
        issuer_document=_normalize_text(payload.get("emitente_cpf_cnpj")),
        cfops=cfops,
        total_amount=_normalize_decimal(payload.get("valor_total")),
        import_source=_normalize_text(payload.get("tipo_importacao")),
        imported=payload.get("importada") if isinstance(payload.get("importada"), bool) else None,
        has_xml=payload.get("tem_xml") if isinstance(payload.get("tem_xml"), bool) else None,
        raw_payload=payload,
    )


def map_task_page(payload: dict[str, Any], *, page_number: int, page_size: int) -> SittaxTaskPage:
    if not isinstance(payload, dict):
        raise SittaxResponseError("Unexpected Sittax task response format.")
    if payload.get("sucesso") is not True:
        raise SittaxBusinessError("Sittax task response returned sucesso=false.")
    lista = payload.get("lista")
    if not isinstance(lista, list):
        raise SittaxResponseError("Sittax task response is missing lista.")

    items = [map_task_item(item) for item in lista if isinstance(item, dict)]
    return SittaxTaskPage(
        page_number=page_number,
        page_size=page_size,
        total=_normalize_int(payload.get("total")),
        total_filtered=_normalize_int(payload.get("totalFiltrado")),
        items=items,
        raw_payload=payload,
    )


def map_task_item(payload: dict[str, Any]) -> SittaxTaskItem:
    sittax_task_id = _normalize_text(payload.get("id"))
    guid = _normalize_text(payload.get("guid"))
    task_name = _normalize_text(payload.get("titulo"))
    status_code = _normalize_optional_int(payload.get("status"))
    file_extension_code = _normalize_optional_int(payload.get("extensaoArquivo"))
    file_name = _normalize_text(payload.get("nomeArquivo"))
    file_extension = _normalize_extension(payload.get("extensaoArquivo"))
    if file_extension is None and file_name and "." in file_name:
        file_extension = "." + file_name.rsplit(".", 1)[-1].lower()
    period_reference = _normalize_period_reference(payload.get("periodo")) if payload.get("periodo") else None
    source_task_key = sittax_task_id or guid
    if source_task_key is None:
        source_task_key = _hash_key(
            [
                task_name or "",
                period_reference or "",
                _normalize_text(payload.get("nomeEmpresa")) or "",
                _normalize_text(payload.get("dataCriacao")) or "",
            ]
        )

    return SittaxTaskItem(
        source_task_key=source_task_key,
        sittax_task_id=sittax_task_id,
        task_type=_normalize_text(payload.get("tipo") or payload.get("tipoNome")) or task_name,
        task_name=task_name,
        description=_normalize_text(payload.get("descricaoString")),
        company_name=_normalize_text(payload.get("nomeEmpresa")),
        company_cnpj=normalize_cnpj(payload.get("empresaCnpj")),
        period_reference=period_reference,
        source_created_at=_normalize_datetime_text(payload.get("dataCriacao")),
        source_finished_at=_normalize_datetime_text(payload.get("dataFimProcessamento")),
        source_user_id=_normalize_text(payload.get("usuarioId")),
        source_user_name=_normalize_text(payload.get("usuarioNome")),
        status=_normalize_text(payload.get("status")),
        status_code=status_code,
        has_file=payload.get("possuiArquivo") if isinstance(payload.get("possuiArquivo"), bool) else None,
        file_name=file_name,
        file_extension=file_extension,
        file_extension_code=file_extension_code,
        processing_time_seconds=_normalize_decimal(payload.get("tempoProcessamento")),
        raw_payload=payload,
    )


def sanitize_contract_message(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    text = re.sub(r"\d", "#", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]
