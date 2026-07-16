from __future__ import annotations

import copy

import pytest

from backend.app.services.integrations.sittax.errors import SittaxBusinessError, SittaxResponseError
from backend.app.services.integrations.sittax.mapper import map_companies_response, map_company_item, map_login_response


@pytest.mark.parametrize("success_code", [0, 200, "0", "200"])
def test_map_login_response_extracts_token_and_office(success_code: int | str) -> None:
    payload = {
        "codigo": success_code,
        "token": "jwt-fixture",
        "usuario": {
            "id": "usr-1",
            "role": "ADMIN",
            "escritorio": {"id": "esc-1", "nome": "Escritorio Exemplo"},
        },
    }

    mapped = map_login_response(payload)

    assert mapped["token"] == "jwt-fixture"
    assert mapped["office"].id == "esc-1"
    assert mapped["user_id"] == "usr-1"


def test_map_login_response_rejects_unexpected_business_code() -> None:
    with pytest.raises(SittaxBusinessError, match="business code 401"):
        map_login_response({"codigo": 401, "token": "jwt-fixture", "usuario": {"escritorio": {"id": "esc-1"}}})


def test_map_company_item_normalizes_cnpj_and_empty_ie() -> None:
    mapped = map_company_item(
        {
            "id": "emp-1",
            "cnpj": "12.345.678/0001-95",
            "nome": "Empresa Exemplo",
            "fantasia": "Empresa",
            "uf": "go",
            "inscricaoEstadual": "   ",
            "homologada": True,
            "usaRegimeDeCaixa": False,
            "extra": "kept",
        }
    )

    assert mapped.cnpj == "12345678000195"
    assert mapped.state_registration is None
    assert mapped.status == "HOMOLOGADA"
    assert mapped.raw_payload["extra"] == "kept"


def test_map_company_item_rejects_invalid_cnpj() -> None:
    with pytest.raises(SittaxResponseError, match="invalid cnpj"):
        map_company_item({"id": "emp-1", "cnpj": "123", "nome": "Empresa Exemplo"})


def test_map_companies_response_preserves_duplicates_and_optional_fields() -> None:
    entry = {
        "id": "emp-1",
        "cnpj": "12345678000195",
        "nome": "Empresa Exemplo",
        "fantasia": None,
        "uf": None,
        "inscricaoEstadual": None,
        "homologada": False,
        "usaRegimeDeCaixa": True,
    }
    payload = {"sucesso": True, "empresas": [entry, copy.deepcopy(entry)]}

    mapped = map_companies_response(payload)

    assert len(mapped) == 2
    assert mapped[0].status == "NAO_HOMOLOGADA"
    assert mapped[0].trade_name is None


def test_map_companies_response_handles_empty_list() -> None:
    assert map_companies_response({"sucesso": True, "empresas": []}) == []


def test_map_companies_response_rejects_business_failure() -> None:
    with pytest.raises(SittaxBusinessError):
        map_companies_response({"sucesso": False, "empresas": []})


def test_map_companies_response_rejects_malformed_payload() -> None:
    with pytest.raises(SittaxResponseError):
        map_companies_response({"sucesso": True, "empresas": [None]})
