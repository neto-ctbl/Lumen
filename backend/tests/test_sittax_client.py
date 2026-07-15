from __future__ import annotations

import json

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.integrations.sittax.client import SittaxClient
from backend.app.services.integrations.sittax.errors import (
    SittaxAuthenticationError,
    SittaxAuthorizationError,
    SittaxBusinessError,
    SittaxConfigurationError,
    SittaxRateLimitError,
    SittaxResponseError,
    SittaxSessionError,
    SittaxTransportError,
)
from backend.app.services.integrations.sittax.session import SittaxSession


def make_session(handler) -> SittaxSession:
    return SittaxSession(
        auth_base_url="https://autenticacao.sittax.com.br",
        api_base_url="https://api.sittax.com.br",
        apuracao_base_url="https://apuracao.sittax.com.br",
        timeout_seconds=20,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_client_authenticates_lists_companies_and_applies_bearer_header() -> None:
    calls: list[str] = []
    auth_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        auth_headers.append(request.headers.get("Authorization"))
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 0,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(
            200,
            json={
                "sucesso": True,
                "empresas": [
                    {
                        "id": "emp-1",
                        "cnpj": "12.345.678/0001-95",
                        "nome": "Empresa Exemplo",
                        "inscricaoEstadual": "",
                        "uf": "GO",
                        "homologada": True,
                        "usaRegimeDeCaixa": False,
                    }
                ],
            },
        )

    session = make_session(handler)
    client = SittaxClient(session=session)

    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        companies = client.list_companies()

    assert session.office_id == "esc-1"
    assert companies[0].cnpj == "12345678000195"
    assert auth_headers[0] is None
    assert auth_headers[1] == "Bearer jwt-secret-token"
    assert all("/api/apuracao/" not in call for call in calls)
    assert all("/api/difal/" not in call for call in calls)
    assert all("/api/nota-fiscal/" not in call for call in calls)
    assert all("/api/v2/painel-contador/transmissao" not in call for call in calls)
    assert all("recalcular=true" not in call for call in calls)


def test_client_does_not_repeat_login_when_session_is_authenticated() -> None:
    login_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_calls
        if request.url.path == "/api/auth/login":
            login_calls += 1
            return httpx.Response(
                200,
                json={
                    "codigo": 0,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(200, json={"sucesso": True, "empresas": []})

    session = make_session(handler)
    client = SittaxClient(session=session)
    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
    assert login_calls == 1


def test_client_requires_credentials_when_using_settings() -> None:
    session = make_session(lambda request: httpx.Response(200, json={}))
    client = SittaxClient(session=session)
    settings = Settings(_env_file=None)

    with session.exclusive():
        with pytest.raises(SittaxConfigurationError, match="SITTAX_EMAIL"):
            client.authenticate_with_settings(settings)


@pytest.mark.parametrize(
    ("status_code", "exc_type"),
    [
        (401, SittaxAuthenticationError),
        (403, SittaxAuthorizationError),
        (429, SittaxRateLimitError),
        (500, SittaxResponseError),
    ],
)
def test_client_maps_http_errors(status_code: int, exc_type: type[Exception]) -> None:
    session = make_session(lambda request: httpx.Response(status_code))
    client = SittaxClient(session=session)

    with session.exclusive():
        with pytest.raises(exc_type):
            client.authenticate(username="usuario@example.invalid", password="senha-secreta")


def test_client_maps_timeout_and_invalid_json_and_business_envelope() -> None:
    timeout_session = make_session(lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("boom")))
    timeout_client = SittaxClient(session=timeout_session)
    with timeout_session.exclusive():
        with pytest.raises(SittaxTransportError):
            timeout_client.authenticate(username="usuario@example.invalid", password="senha-secreta")

    invalid_json_session = make_session(lambda request: httpx.Response(200, content=b"{invalid json"))
    invalid_json_client = SittaxClient(session=invalid_json_session)
    with invalid_json_session.exclusive():
        with pytest.raises(SittaxResponseError):
            invalid_json_client.authenticate(username="usuario@example.invalid", password="senha-secreta")

    business_session = make_session(
        lambda request: httpx.Response(200, json={"codigo": 9, "usuario": {}, "token": None})
    )
    business_client = SittaxClient(session=business_session)
    with business_session.exclusive():
        with pytest.raises(SittaxBusinessError):
            business_client.authenticate(username="usuario@example.invalid", password="senha-secreta")


def test_client_rejects_malformed_companies_response_and_closed_session() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(
                200,
                json={
                    "codigo": 0,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(200, json={"sucesso": True, "empresas": [None]})

    session = make_session(handler)
    client = SittaxClient(session=session)
    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")
        with pytest.raises(SittaxResponseError):
            client.list_companies()

    client.close()
    with pytest.raises(SittaxSessionError, match="closed"):
        with session.exclusive():
            pass


def test_client_repr_does_not_expose_sensitive_values() -> None:
    session = make_session(lambda request: httpx.Response(200, json={}))
    client = SittaxClient(session=session)

    assert "senha" not in repr(client).lower()
    assert "token" not in repr(client).lower()


def test_client_sends_observed_login_body_keys_only() -> None:
    seen_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            seen_body.update(json.loads(request.content.decode("utf-8")))
            return httpx.Response(
                200,
                json={
                    "codigo": 0,
                    "token": "jwt-secret-token",
                    "usuario": {"id": "usr-1", "role": "ADMIN", "escritorio": {"id": "esc-1", "nome": "Esc"}},
                },
            )
        return httpx.Response(200, json={"sucesso": True, "empresas": []})

    session = make_session(handler)
    client = SittaxClient(session=session)
    with session.exclusive():
        client.authenticate(username="usuario@example.invalid", password="senha-secreta")

    assert sorted(seen_body.keys()) == ["senha", "usuario"]
