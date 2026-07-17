from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.services.integrations.sittax.errors import SittaxContextMismatchError, SittaxResponseError
from backend.app.services.integrations.sittax.mapper import map_apuracao_response


def _payload() -> dict:
    return {
        "ok": True,
        "status": 200,
        "erros": [],
        "data": {
            "id": "apur-sint-2026-06-001",
            "empresaNome": "EMPRESA EXEMPLO A LTDA",
            "escritorioNome": "ESCRITORIO EXEMPLO",
            "periodoFiscal": {
                "dataInicial": "2026-06-01T00:00:00",
                "dataFinal": "2026-06-30T23:59:59.999",
                "id": "periodo-sint-2026-06",
            },
            "valorDas": "1834.77",
            "valorDasXml": 1834.77,
            "numeroDas": "DAS-SINT-202606-001",
            "numeroDeclaracao": "DECL-SINT-202606-001",
            "numeroExtrato": "EXT-SINT-202606-001",
            "rba": "352400.12",
            "rbt12": 486122.43,
            "receitaLiquida": 40221.76,
            "receitaProdutos": 15780.13,
            "receitaServicos": 24441.63,
            "receitaDevolucao": 0,
            "folhaDePagamentos": True,
            "percentualFatorR": 31.42,
            "tipoDaTransmissao": "TRANSMITIDA",
            "dataHoraTransmissao": "2026-07-07T17:35:10",
            "mensagens": [{"tipo": "ALERTA", "texto": "Mensagem sintetica de conferencia."}],
            "inconsistencias": [],
            "empresasApuracao": [
                {
                    "cnpj": "12345678000195",
                    "nome": "EMPRESA EXEMPLO A LTDA",
                    "empresaTemFolha": True,
                    "empresaTributaIcms": True,
                    "empresaTributaIss": False,
                    "empresaTributaIpi": False,
                    "empresaTributaPisCofins": True,
                    "atividades": ["6201501"],
                    "resumoPorCfop": [{"cfop": "5102", "valor": 24441.63}],
                    "valoresXml": [{"anexoApuracao": {"codigo": 3, "nome": "Anexo III"}, "valorDas": 1834.77}],
                }
            ],
            "resumosTributacaoSittax": [{"anexo": "ANEXO_III", "aliquotaEfetiva": 6.15, "receita": 24441.63}],
            "resumosTributacaoXml": [],
            "relatorioDeConferenciaSittax": {"possuiRisco": True, "itens": 2},
        },
    }


def test_map_apuracao_response_normalizes_decimals_and_blocks() -> None:
    mapped = map_apuracao_response(
        _payload(),
        requested_company_cnpj="12345678000195",
        requested_period="2026-06",
    )

    assert mapped.confirmed_period == "2026-06"
    assert mapped.das_amount == Decimal("1834.77")
    assert mapped.rba == Decimal("352400.12")
    assert mapped.company_has_payroll is True
    assert mapped.is_transmitted is True
    assert mapped.transmission_type == "TRANSMITIDA"
    assert mapped.annexes[0]["anexo"] == "ANEXO_III"
    assert mapped.cfops[0]["cfop"] == "5102"
    assert mapped.activities[0]["code"] == "6201501"
    assert mapped.alerts[0]["tipo"] == "ALERTA"
    assert mapped.risks[0]["possuiRisco"] is True


def test_map_apuracao_response_rejects_context_mismatch() -> None:
    payload = _payload()
    payload["data"]["empresaCnpj"] = "99999999000199"

    with pytest.raises(SittaxContextMismatchError):
        map_apuracao_response(
            payload,
            requested_company_cnpj="12345678000195",
            requested_period="2026-06",
        )


def test_map_apuracao_response_rejects_invalid_period_and_numeric() -> None:
    bad_period = _payload()
    bad_period["data"]["periodoFiscal"] = {"id": "invalid"}
    with pytest.raises(SittaxResponseError):
        map_apuracao_response(
            bad_period,
            requested_company_cnpj="12345678000195",
            requested_period="2026-06",
        )


def test_map_apuracao_response_uses_nested_company_context_when_root_cnpj_is_missing() -> None:
    payload = _payload()
    payload["data"].pop("empresaNome", None)

    mapped = map_apuracao_response(
        payload,
        requested_company_cnpj="12345678000195",
        requested_period="2026-06",
    )

    assert mapped.confirmed_company_cnpj == "12345678000195"
    assert mapped.company_name == "EMPRESA EXEMPLO A LTDA"

    bad_numeric = _payload()
    bad_numeric["data"]["valorDas"] = "abc"
    with pytest.raises(SittaxResponseError):
        map_apuracao_response(
            bad_numeric,
            requested_company_cnpj="12345678000195",
            requested_period="2026-06",
        )
