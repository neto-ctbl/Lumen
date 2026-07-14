from __future__ import annotations

from datetime import date

import pytest

from backend.app.core.enums import ReconciliationStatus
from backend.app.services.integrations.acessorias.mapper import (
    AcessoriasMappingError,
    map_company_payload,
    map_delivery_company_block,
    map_delivery_payload,
    normalize_acessorias_date,
    normalize_acessorias_datetime,
    normalize_delivery_status,
    normalize_identifier,
)


def test_map_company_payload_maps_documented_regime_textual() -> None:
    payload = {
        "ID": "1",
        "Identificador": "11.111.111/0001-11",
        "Razao": "Alpha Ltda",
        "Fantasia": "Alpha",
        "Status": "Ativa",
        "Regime": "Lucro Real",
    }

    mapped = map_company_payload(payload)

    assert mapped["external_company_id"] == "1"
    assert mapped["identifier"] == "11111111000111"
    assert mapped["regime_canonical"] == "LUCRO_REAL"
    assert mapped["regime_mapping_status"] == "MAPPED"


def test_map_company_payload_keeps_unknown_regime_unmapped() -> None:
    mapped = map_company_payload(
        {
            "ID": "1",
            "Identificador": "11.111.111/0001-11",
            "Razao": "Alpha Ltda",
            "Regime": "Produtor Rural",
        }
    )

    assert mapped["regime_canonical"] is None
    assert mapped["regime_mapping_status"] == "UNMAPPED"


def test_normalizers_convert_zero_dates_to_none() -> None:
    assert normalize_acessorias_date("0000-00-00") is None
    assert normalize_acessorias_datetime("0000-00-00 00:00:00") is None


def test_map_delivery_payload_maps_finalized_delivery() -> None:
    company = map_delivery_company_block(
        {"ID": "9001", "Identificador": "11.111.111/0001-11", "Razao": "Alpha Ltda"}
    )
    mapped = map_delivery_payload(
        company,
        {
            "Nome": "DAS",
            "EntDtPrazo": "2026-06-20",
            "EntDtAtraso": "2026-06-21",
            "EntDtEntrega": "2026-06-18",
            "EntDtFinalizacao": "2026-06-18 10:30:00",
            "Status": "Ent. antecipada",
            "EntLastDH": "2026-06-18 10:30:00",
            "EntMulta": "N",
            "EntGuiaLida": "S",
            "Config": {"EntID": "5001", "Tipo": "O", "ID": "100", "DptoNome": "Fiscal"},
        },
    )

    assert mapped["external_delivery_id"] == "5001"
    assert mapped["normalized_status"] == ReconciliationStatus.CONFIRMADO_API.value
    assert mapped["due_date"] == date(2026, 6, 20)
    assert mapped["has_penalty"] is False


def test_normalize_delivery_status_pending_and_late_stay_pending() -> None:
    payload = {
        "Status": "Atrasada!",
        "EntDtEntrega": "0000-00-00",
        "EntDtFinalizacao": None,
    }

    assert normalize_delivery_status(payload) == ReconciliationStatus.PENDENTE.value


def test_map_delivery_payload_preserves_task_type() -> None:
    company = map_delivery_company_block(
        {"ID": "9001", "Identificador": "11.111.111/0001-11", "Razao": "Alpha Ltda"}
    )
    mapped = map_delivery_payload(
        company,
        {
            "Nome": "Consulta do e-Social!",
            "EntDtPrazo": "2026-06-20",
            "EntDtEntrega": "0000-00-00",
            "EntDtFinalizacao": None,
            "Status": "Pendente",
            "EntLastDH": "2026-06-18 10:30:00",
            "Config": {"EntID": "5003", "Tipo": "T", "ID": "102"},
        },
    )

    assert mapped["external_type"] == "T"
    assert mapped["normalized_status"] == ReconciliationStatus.PENDENTE.value


def test_map_delivery_payload_raises_when_required_field_missing() -> None:
    company = map_delivery_company_block(
        {"ID": "9001", "Identificador": "11.111.111/0001-11", "Razao": "Alpha Ltda"}
    )

    with pytest.raises(AcessoriasMappingError):
        map_delivery_payload(company, {"Status": "Pendente", "Config": {"EntID": "5001"}})


def test_normalize_identifier_strips_non_digits() -> None:
    assert normalize_identifier("11.111.111/0001-11") == "11111111000111"
