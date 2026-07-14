from __future__ import annotations

from datetime import date

import httpx
import pytest

from backend.app.services.integrations.acessorias.client import (
    AcessoriasAuthenticationError,
    AcessoriasClient,
    AcessoriasNotFoundError,
    AcessoriasRateLimitError,
    AcessoriasResponseError,
    AcessoriasTransportError,
)


def test_client_sends_bearer_and_presence_flags_without_value() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[])

    client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    list(client.iter_companies())

    assert seen["auth"] == "Bearer secret-token"
    assert "registrationData" in seen["url"]
    assert "registrationData=" not in seen["url"]


def test_client_paginates_until_empty_list() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if "Pagina=1" in str(request.url):
            return httpx.Response(200, json=[{"ID": "1", "Identificador": "1", "Razao": "A"}])
        return httpx.Response(200, json=[])

    client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    items = list(client.iter_companies())

    assert len(items) == 1
    assert len(requests) == 2


def test_client_handles_204_as_empty_list() -> None:
    client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(204))),
    )

    assert client.get_deliveries("111", dt_initial=date(2026, 6, 1), dt_final=date(2026, 6, 30), page=1) == []


@pytest.mark.parametrize(
    ("status_code", "exc_type"),
    [
        (401, AcessoriasAuthenticationError),
        (403, AcessoriasAuthenticationError),
        (404, AcessoriasNotFoundError),
        (429, AcessoriasRateLimitError),
    ],
)
def test_client_maps_http_errors(status_code: int, exc_type: type[Exception]) -> None:
    client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status_code))),
    )

    with pytest.raises(exc_type):
        client.get_company("ListAll")


def test_client_raises_for_business_error_and_invalid_json() -> None:
    business_client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"Erro": "Falha"}))
        ),
    )
    invalid_json_client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{invalid json"))
        ),
    )

    with pytest.raises(AcessoriasResponseError):
        business_client.get_company("ListAll")
    with pytest.raises(AcessoriasResponseError):
        invalid_json_client.get_company("ListAll")


def test_client_maps_timeout_and_rate_limit_spacing() -> None:
    sleeps: list[float] = []
    monotonic_values = iter([0.0, 0.0, 0.1, 0.1, 0.7, 0.7])

    def raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom")

    timeout_client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(raise_timeout)),
    )
    with pytest.raises(AcessoriasTransportError):
        timeout_client.get_company("ListAll")

    serial_client = AcessoriasClient(
        base_url="https://api.acessorias.com",
        token="secret-token",
        timeout_seconds=15,
        requests_per_minute=100,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))),
        monotonic=lambda: next(monotonic_values),
        sleep=lambda seconds: sleeps.append(seconds),
    )

    serial_client.get_company("ListAll")
    serial_client.get_company("ListAll")

    assert sleeps
    assert sleeps[0] > 0
