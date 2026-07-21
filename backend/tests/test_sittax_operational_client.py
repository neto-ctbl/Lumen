from __future__ import annotations

from urllib.parse import parse_qs

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


def test_client_get_difal_requires_context_and_sends_recalcular_false() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/api/difal/obter-valores-difal":
            query = parse_qs(request.url.query.decode("utf-8"))
            assert query["recalcular"] == ["false"]
            return httpx.Response(
                200,
                json={"sucesso": True, "mensagem": None, "possuiMensagemDeAlerta": False, "difal": {"id": "difal-1"}},
            )
        raise AssertionError(request.url.path)

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(
            token="jwt",
            office_id="esc-1",
            office_name="Esc",
            user_id="usr-1",
            user_role="ADMIN",
        )
        with pytest.raises(SittaxContextMismatchError):
            client.get_difal(company_cnpj="12345678000195", period="2026-06")
        session.set_api_context(company_cnpj="12345678000195", period="2026-06")
        mapped = client.get_difal(company_cnpj="12345678000195", period="2026-06")

    assert mapped.difal_id == "difal-1"
    assert calls == ["https://api.sittax.com.br/api/difal/obter-valores-difal?recalcular=false"]


def test_client_paginate_tasks_fetches_multiple_pages_until_total_filtered() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path != "/api/tarefa/paginacao":
            raise AssertionError(request.url.path)
        query = parse_qs(request.url.query.decode("utf-8"))
        page_number = int(query.get("pagina", ["0"])[0])
        return httpx.Response(
            200,
            json={
                "sucesso": True,
                "total": 3,
                "totalFiltrado": 3,
                "lista": [{"id": f"task-{page_number + 1}", "titulo": f"Tarefa {page_number + 1}", "periodo": "06/2026"}],
            },
        )

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        session.mark_authenticated(
            token="jwt",
            office_id="esc-1",
            office_name="Esc",
            user_id="usr-1",
            user_role="ADMIN",
        )
        pages = client.paginate_tasks(page_size=1, max_pages=5)

    assert [len(page.items) for page in pages] == [1, 1, 1]
    assert len(calls) == 3
