from __future__ import annotations

import httpx
import pytest

from backend.app.services.integrations.sittax.client import SittaxClient
from backend.app.services.integrations.sittax.errors import SittaxContextMismatchError
from backend.app.services.integrations.sittax.session import SittaxSession


def make_session(handler) -> SittaxSession:
    return SittaxSession(
        auth_base_url="https://autenticacao.sittax.com.br",
        api_base_url="https://api.sittax.com.br",
        apuracao_base_url="https://apuracao.sittax.com.br",
        timeout_seconds=20,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_ensure_api_context_replays_observed_sequence() -> None:
    calls: list[tuple[str, str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.headers.get("cookie"), request.content.decode("utf-8") or None))
        if request.url.path == "/api/v2/painel-contador/valor-auditoria":
            return httpx.Response(200, json={"ok": True, "status": 200, "erros": [], "data": {}})
        if request.url.path == "/api/painelprincipal/retornar-dados-por-empresa":
            return httpx.Response(200, json={"$id": "1", "sucesso": True, "nome": "EMPRESA", "alertas": []})
        raise AssertionError(request.url.path)

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(token="jwt", office_id="esc-1", office_name="Esc", user_id="usr-1", user_role="ADMIN")
        session.set_apuracao_context(company_cnpj="12345678000195", period="2026-06")
        client.ensure_api_context(company_cnpj="12345678000195", period="2026-06")

    assert session.active_api_company_cnpj == "12345678000195"
    assert session.active_api_period == "2026-06"
    assert calls == [
        (
            "POST",
            "/api/v2/painel-contador/valor-auditoria",
            "CnpjDaEmpresaSelecionada=12345678000195; DataInicialSelecionada=2026-06-01T00:00:00; IdEscritorioSelecionado=esc-1; IdGrupoDeEmpresaSelecionado=",
            '{"periodo":"06/2026"}',
        ),
        (
            "GET",
            "/api/painelprincipal/retornar-dados-por-empresa",
            "CnpjDaEmpresaSelecionada=12345678000195; DataInicialSelecionada=2026-06-01T00:00:00; IdEscritorioSelecionado=esc-1; IdGrupoDeEmpresaSelecionado=",
            None,
        ),
    ]


def test_ensure_api_context_clears_api_side_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/painel-contador/valor-auditoria":
            return httpx.Response(200, json={"ok": True, "status": 200, "erros": [], "data": {}})
        if request.url.path == "/api/painelprincipal/retornar-dados-por-empresa":
            return httpx.Response(200, json={"$id": "1", "sucesso": False, "mensagem": "Favor Selecionar a Empresa", "status": False})
        raise AssertionError(request.url.path)

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(token="jwt", office_id="esc-1", office_name="Esc", user_id="usr-1", user_role="ADMIN")
        session.set_apuracao_context(company_cnpj="12345678000195", period="2026-06")
        with pytest.raises(SittaxContextMismatchError):
            client.ensure_api_context(company_cnpj="12345678000195", period="2026-06")

    assert session.active_api_company_cnpj is None
    assert session.active_api_period is None
    assert session.http_client.cookies.get("CnpjDaEmpresaSelecionada") is None
    assert session.http_client.cookies.get("DataInicialSelecionada") is None


def test_difal_and_documents_require_api_context_not_only_apuracao_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected outbound call: {request.url.path}")

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(token="jwt", office_id="esc-1", office_name="Esc", user_id="usr-1", user_role="ADMIN")
        session.set_apuracao_context(company_cnpj="12345678000195", period="2026-06")
        with pytest.raises(SittaxContextMismatchError):
            client.get_difal(company_cnpj="12345678000195", period="2026-06")
        with pytest.raises(SittaxContextMismatchError):
            client.list_fiscal_documents_entry_page(
                company_cnpj="12345678000195",
                period="2026-06",
                page_number=0,
                page_size=15,
            )


def test_apuracao_context_seeds_observed_company_period_cookies() -> None:
    session = make_session(lambda request: httpx.Response(200, json={}))

    with session.exclusive():
        session.set_apuracao_context(company_cnpj="12345678000195", period="2026-06")

    assert session.http_client.cookies.get("CnpjDaEmpresaSelecionada") == "12345678000195"
    assert session.http_client.cookies.get("DataInicialSelecionada") == "2026-06-01T00:00:00"
