from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest

from backend.app.services.integrations.sittax.client import SittaxClient
from backend.app.services.integrations.sittax.errors import SittaxContextMismatchError, SittaxResponseError, SittaxTransportError
from backend.app.services.integrations.sittax.session import SittaxSession


def make_session(handler) -> SittaxSession:
    return SittaxSession(
        auth_base_url="https://autenticacao.sittax.com.br",
        api_base_url="https://api.sittax.com.br",
        apuracao_base_url="https://apuracao.sittax.com.br",
        timeout_seconds=20,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_client_get_apuracao_uses_expected_endpoint_and_updates_context() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 200,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        if request.url.path == "/api/apuracao/retornar-apuracao-sittax":
            query = parse_qs(request.url.query.decode("utf-8"))
            assert query["empresaCnpj"] == ["12345678000195"]
            assert query["periodo"] == ["06/2026"]
            return httpx.Response(
                200,
                json=json.dumps({
                    "ok": True,
                    "status": 200,
                    "erros": [],
                    "data": {
                        "id": "apur-1",
                        "periodoFiscal": {
                            "dataInicial": "2026-06-01T00:00:00",
                            "dataFinal": "2026-06-30T23:59:59.999",
                        },
                        "valorDas": 10,
                        "rba": 20,
                        "rbt12": 30,
                        "empresasApuracao": [
                            {
                                "cnpj": "12345678000195",
                                "nome": "Empresa Exemplo",
                                "empresaTributaIcms": True,
                                "empresaTributaIss": False,
                                "empresaTributaIpi": False,
                                "empresaTributaPisCofins": True,
                            }
                        ],
                        "mensagens": [],
                        "inconsistencias": [],
                        "resumosTributacaoSittax": [],
                        "resumosTributacaoXml": [],
                    },
                }),
            )
        raise AssertionError(request.url.path)

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        mapped = client.get_apuracao(company_cnpj="12.345.678/0001-95", period="2026-06")

    assert mapped.confirmed_period == "2026-06"
    assert session.active_company_cnpj == "12345678000195"
    assert session.active_period == "2026-06"
    assert calls == [
        "https://autenticacao.sittax.com.br/api/auth/login",
        "https://apuracao.sittax.com.br/api/apuracao/retornar-apuracao-sittax?empresaCnpj=12345678000195&periodo=06%2F2026",
    ]


def test_client_get_apuracao_clears_context_on_failures() -> None:
    def mismatch_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 200,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "status": 200,
                "erros": [],
                "data": {
                    "id": "apur-1",
                    "periodoFiscal": "06/2026",
                    "valorDas": 10,
                    "rba": 20,
                    "rbt12": 30,
                    "empresasApuracao": [{"cnpj": "99999999000199"}],
                    "mensagens": [],
                    "inconsistencias": [],
                    "resumosTributacaoSittax": [],
                    "resumosTributacaoXml": [],
                },
            },
        )

    mismatch_session = make_session(mismatch_handler)
    mismatch_client = SittaxClient(session=mismatch_session)
    with mismatch_session.exclusive():
        mismatch_client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        with pytest.raises(SittaxContextMismatchError):
            mismatch_client.get_apuracao(company_cnpj="12345678000195", period="2026-06")
        assert mismatch_session.active_company_cnpj is None
        assert mismatch_session.active_period is None

    timeout_session = make_session(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("boom")))
    timeout_client = SittaxClient(session=timeout_session)
    with timeout_session.exclusive():
        timeout_client.session.mark_authenticated(
            token="jwt",
            office_id="esc-1",
            office_name="Esc",
            user_id="usr-1",
            user_role="ADMIN",
        )
        with pytest.raises(SittaxTransportError):
            timeout_client.get_apuracao(company_cnpj="12345678000195", period="2026-06")
        assert timeout_session.active_company_cnpj is None
        assert timeout_session.active_period is None


def test_client_get_apuracao_rejects_invalid_interface_period() -> None:
    session = make_session(lambda request: httpx.Response(200, json={}))
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(
            token="jwt",
            office_id="esc-1",
            office_name="Esc",
            user_id="usr-1",
            user_role="ADMIN",
        )
        with pytest.raises(SittaxResponseError):
            client.get_apuracao(company_cnpj="12345678000195", period="06/2026")


def test_client_rejects_invalid_nested_json_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 200,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(200, json="{invalid")

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        with pytest.raises(SittaxResponseError, match="nested JSON"):
            client.get_apuracao(company_cnpj="12345678000195", period="2026-06")
