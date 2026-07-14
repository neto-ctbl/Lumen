from __future__ import annotations

import unicodedata
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from backend.app.core.enums import ReconciliationStatus

from backend.app.services.integrations.acessorias.regime import resolve_acessorias_regime


class AcessoriasMappingError(ValueError):
    pass


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_label(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    ).upper()


def normalize_identifier(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or text


def normalize_acessorias_date(value: Any) -> date | None:
    text = _normalize_text(value)
    if text is None or text == "0000-00-00":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise AcessoriasMappingError(f"Invalid date value: {text}") from exc


def normalize_acessorias_datetime(value: Any) -> datetime | None:
    text = _normalize_text(value)
    if text is None or text == "0000-00-00" or text == "0000-00-00 00:00:00":
        return None
    normalized = text.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AcessoriasMappingError(f"Invalid datetime value: {text}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def normalize_delivery_status(payload: dict[str, Any]) -> str:
    finalized_at = normalize_acessorias_datetime(payload.get("EntDtFinalizacao"))
    delivered_date = normalize_acessorias_date(payload.get("EntDtEntrega"))
    label = _normalize_label(payload.get("Status"))

    if finalized_at is not None or delivered_date is not None:
        if label in {None, "PENDENTE", "ATRASADA!"}:
            return ReconciliationStatus.CONFERENCIA_MANUAL.value
        return ReconciliationStatus.CONFIRMADO_API.value

    if label in {None, "PENDENTE", "ATRASADA!"}:
        return ReconciliationStatus.PENDENTE.value

    if label in {"ENT. ANTECIPADA", "ENTREGUE"}:
        return ReconciliationStatus.CONFERENCIA_MANUAL.value

    return ReconciliationStatus.CONFERENCIA_MANUAL.value


def _require(payload: dict[str, Any], field: str) -> Any:
    if field not in payload:
        raise AcessoriasMappingError(f"Missing required field: {field}")
    return payload[field]


def map_company_payload(payload: dict[str, Any], *, retrieved_at: datetime | None = None) -> dict[str, Any]:
    external_company_id = _normalize_text(_require(payload, "ID"))
    identifier = normalize_identifier(_require(payload, "Identificador"))
    razao_social = _normalize_text(_require(payload, "Razao"))
    if external_company_id is None or identifier is None or razao_social is None:
        raise AcessoriasMappingError("Company payload is missing required values.")

    regime_raw = _normalize_text(payload.get("Regime"))
    regime = resolve_acessorias_regime(regime_raw)

    return {
        "external_company_id": external_company_id,
        "identifier": identifier,
        "razao_social": razao_social,
        "nome_fantasia": _normalize_text(payload.get("Fantasia")),
        "external_status": _normalize_text(payload.get("Status")),
        "regime_raw": regime.raw,
        "regime_code": regime.code,
        "regime_canonical": regime.canonical,
        "regime_mapping_status": regime.mapping_status,
        "raw_payload": payload,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc),
    }


@dataclass(slots=True)
class DeliveryCompanyBlock:
    external_company_id: str
    identifier: str
    razao_social: str
    nome_fantasia: str | None


def map_delivery_company_block(payload: dict[str, Any]) -> DeliveryCompanyBlock:
    external_company_id = _normalize_text(_require(payload, "ID"))
    identifier = normalize_identifier(_require(payload, "Identificador"))
    razao_social = _normalize_text(_require(payload, "Razao"))
    if external_company_id is None or identifier is None or razao_social is None:
        raise AcessoriasMappingError("Delivery company block is missing required values.")
    return DeliveryCompanyBlock(
        external_company_id=external_company_id,
        identifier=identifier,
        razao_social=razao_social,
        nome_fantasia=_normalize_text(payload.get("Fantasia")),
    )


def map_delivery_payload(
    company_block: dict[str, Any] | DeliveryCompanyBlock,
    payload: dict[str, Any],
    *,
    retrieved_at: datetime | None = None,
) -> dict[str, Any]:
    block = company_block if isinstance(company_block, DeliveryCompanyBlock) else map_delivery_company_block(company_block)
    config = payload.get("Config")
    if not isinstance(config, dict):
        raise AcessoriasMappingError("Delivery payload is missing Config.")

    external_delivery_id = _normalize_text(config.get("EntID"))
    obligation_name = _normalize_text(_require(payload, "Nome"))
    if external_delivery_id is None or obligation_name is None:
        raise AcessoriasMappingError("Delivery payload is missing required values.")

    has_penalty_raw = _normalize_text(payload.get("EntMulta"))
    has_penalty = None if has_penalty_raw is None else has_penalty_raw.upper() == "S"

    return {
        "external_company_id": block.external_company_id,
        "identifier": block.identifier,
        "external_delivery_id": external_delivery_id,
        "external_item_id": _normalize_text(config.get("ID")),
        "external_type": _normalize_text(config.get("Tipo")),
        "obligation_name": obligation_name,
        "external_status": _normalize_text(payload.get("Status")),
        "normalized_status": normalize_delivery_status(payload),
        "competencia_raw": _normalize_text(payload.get("EntCompetencia")),
        "due_date": normalize_acessorias_date(payload.get("EntDtPrazo")),
        "delay_date": normalize_acessorias_date(payload.get("EntDtAtraso")),
        "delivered_date": normalize_acessorias_date(payload.get("EntDtEntrega")),
        "finalized_at": normalize_acessorias_datetime(payload.get("EntDtFinalizacao")),
        "external_last_changed_at": normalize_acessorias_datetime(payload.get("EntLastDH")),
        "guide_read_status": _normalize_text(payload.get("EntGuiaLida")),
        "has_penalty": has_penalty,
        "department_external_id": _normalize_text(config.get("DptoID")),
        "department_name": _normalize_text(config.get("DptoNome")),
        "responsible_deadline_id": _normalize_text(config.get("RespPrazoID")),
        "responsible_deadline_name": _normalize_text(config.get("RespPrazo")),
        "responsible_delivery_id": _normalize_text(config.get("RespEntregaID")),
        "responsible_delivery_name": _normalize_text(config.get("RespEntrega") or payload.get("RespEntrega")),
        "raw_payload": {"company": asdict(block), "delivery": payload},
        "retrieved_at": retrieved_at or datetime.now(timezone.utc),
    }
