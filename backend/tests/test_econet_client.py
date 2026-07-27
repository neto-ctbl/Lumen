from __future__ import annotations

import inspect

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.services.integrations.econet.assisted_session import get_econet_assisted_session, reset_econet_assisted_session
from backend.app.services.integrations.econet.client import ABAS_PATH, INDEX_PATH, SEARCH_PATH, SUB_ABAS_PATH, EconetClient
from backend.app.services.integrations.econet.encoding import decode_econet_html
from backend.app.services.integrations.econet.errors import (
    EconetHtmlDecodingError,
    EconetSessionExpiredError,
    EconetSessionInvalidError,
    EconetSessionNotLoadedError,
    EconetTransportError,
    EconetUnexpectedContentTypeError,
    EconetUnexpectedRedirectError,
)


def build_settings() -> Settings:
    reset_econet_assisted_session()
    return Settings(
        database_url="postgresql+psycopg://lumen:lumen@localhost:5435/lumen",
        test_database_url="postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test",
        econet_assisted_session_enabled=True,
    )


def load_session(settings: Settings) -> None:
    get_econet_assisted_session(settings).import_storage_state(
        {
            "cookies": [
                {
                    "name": "PHPSESSID",
                    "value": "secret-cookie-value",
                    "domain": ".econeteditora.com.br",
                    "path": "/",
                }
            ]
        }
    )


def test_client_requires_loaded_session() -> None:
    settings = build_settings()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="Consulta por CNAE", headers={"content-type": "text/html"}))
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetSessionNotLoadedError):
        client.probe_session()


def test_probe_valid_session() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="<html>Consulta por CNAE</html>", headers={"content-type": "text/html"}))
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    snapshot = client.probe_session()
    assert snapshot["status"] == "VALID"


@pytest.mark.parametrize("status_code", [401, 403])
def test_probe_marks_expired_on_auth_status(status_code: int) -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(status_code))
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetSessionExpiredError):
        client.probe_session()
    assert get_econet_assisted_session(settings).snapshot()["status"] == "EXPIRED"


def test_probe_marks_expired_on_login_redirect() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "https://www.econeteditora.com.br/login"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetSessionExpiredError):
        client.probe_session()


def test_probe_marks_expired_on_login_html() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html><form>Login <input type='password'/></form></html>", headers={"content-type": "text/html"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetSessionExpiredError):
        client.probe_session()


def test_probe_marks_expired_on_captcha_html() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="<html>captcha</html>", headers={"content-type": "text/html"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetSessionExpiredError):
        client.probe_session()


def test_probe_does_not_follow_redirect() -> None:
    settings = build_settings()
    load_session(settings)
    client = EconetClient(
        settings=settings,
        http_client=httpx.Client(
            base_url=settings.econet_base_url,
            transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": "https://www.econeteditora.com.br/login"})),
            follow_redirects=False,
        ),
    )
    with pytest.raises(EconetSessionExpiredError):
        client.probe_session()


def test_probe_rejects_external_redirect() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": "https://example.com/login"}))
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetUnexpectedRedirectError):
        client.probe_session()


def test_probe_marks_transport_error_without_expiring() -> None:
    settings = build_settings()
    load_session(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(handler)))
    with pytest.raises(EconetTransportError):
        client.probe_session()
    assert get_econet_assisted_session(settings).snapshot()["status"] == "ERROR"


def test_probe_rejects_unexpected_content_type() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text='{"ok":true}', headers={"content-type": "application/json"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetUnexpectedContentTypeError):
        client.probe_session()


def test_search_cnae_uses_fixed_path() -> None:
    settings = build_settings()
    load_session(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == SEARCH_PATH
        return httpx.Response(200, text="<html>idcnae CNAE</html>", headers={"content-type": "text/html"})

    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(handler)))
    client.search_cnae("6201501")


def test_client_decodes_cp1252_html_before_validation() -> None:
    settings = build_settings()
    load_session(settings)
    html = "<html><body>Condição do Simples Nacional - não há impedimento à opção pelo Simples Nacional.</body></html>"
    payload = html.encode("cp1252")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=payload, headers={"content-type": "text/html"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    body = client.get_simples_nacional("999999")
    assert "Condição do Simples Nacional" in body
    assert "não há impedimento" in body


def test_decode_econet_html_uses_declared_utf8() -> None:
    html = "<html><body>serviços técnicos</body></html>"
    assert decode_econet_html(html.encode("utf-8"), "text/html; charset=utf-8") == html


def test_decode_econet_html_uses_meta_charset() -> None:
    html = '<html><head><meta charset="windows-1252"></head><body>gestão técnica</body></html>'
    assert "gestão técnica" in decode_econet_html(html.encode("cp1252"), "text/html")


def test_decode_econet_html_falls_back_to_windows_1252() -> None:
    html = "<html><body>construção e serviços</body></html>"
    assert decode_econet_html(html.encode("cp1252"), "text/html") == html


def test_decode_preserves_portuguese_accents() -> None:
    html = "<html><body>gestão técnica serviços construção não</body></html>"
    decoded = decode_econet_html(html.encode("cp1252"), "text/html")
    assert "gestão" in decoded
    assert "técnica" in decoded
    assert "serviços" in decoded
    assert "construção" in decoded
    assert "não" in decoded


def test_decode_never_returns_replacement_character() -> None:
    html = "<html><body>gestão empresarial</body></html>"
    decoded = decode_econet_html(html.encode("cp1252"), "text/html")
    assert "\ufffd" not in decoded


def test_decode_raises_when_no_safe_decoding_exists() -> None:
    with pytest.raises(EconetHtmlDecodingError):
        decode_econet_html(b"\x81\x8d\x8f\x90\x9d", "text/html; charset=cp1252")


def test_client_does_not_use_httpx_response_text_directly() -> None:
    source = inspect.getsource(EconetClient._request_html) + inspect.getsource(EconetClient._decode_html_response)
    assert ".text" not in source


def test_decoding_error_does_not_expose_html() -> None:
    settings = build_settings()
    load_session(settings)
    payload = b"\x81\x8d\x8f\x90\x9d"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=payload, headers={"content-type": "text/html; charset=cp1252"})
    )
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetHtmlDecodingError) as excinfo:
        client.probe_session()
    assert "<html" not in str(excinfo.value).lower()
    assert "phpessid" not in str(excinfo.value).lower()


def test_detail_uses_fixed_path() -> None:
    settings = build_settings()
    load_session(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == INDEX_PATH
        assert request.url.params["acao"] == "abrir"
        return httpx.Response(200, text="<html>Consulta por CNAE CNAE:</html>", headers={"content-type": "text/html"})

    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(handler)))
    client.get_cnae_detail("999999")


def test_tax_tabs_use_allowlisted_values() -> None:
    settings = build_settings()
    load_session(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == SUB_ABAS_PATH
        assert request.url.params["aba"] == "lucroPresumido"
        return httpx.Response(200, text="<html>lucro presumido CNAE</html>", headers={"content-type": "text/html"})

    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(handler)))
    client.get_lucro_presumido("999999")


def test_obligation_tabs_use_fixed_values() -> None:
    settings = build_settings()
    load_session(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == ABAS_PATH
        assert request.url.params["aba"] == "obrigacoes"
        return httpx.Response(200, text="<html>pj em geral optante simples nacional optante simei</html>", headers={"content-type": "text/html"})

    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(handler)))
    client.get_obligation_tabs("999999")


def test_client_rejects_arbitrary_url() -> None:
    settings = build_settings()
    load_session(settings)
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=httpx.MockTransport(lambda request: httpx.Response(200))))
    with pytest.raises(EconetSessionInvalidError):
        client._request_html("/other/path", params=None, expected_markers=("ok",))


def test_errors_do_not_include_cookie_values() -> None:
    settings = build_settings()
    load_session(settings)
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": "https://example.com/login"}))
    client = EconetClient(settings=settings, http_client=httpx.Client(base_url=settings.econet_base_url, transport=transport))
    with pytest.raises(EconetUnexpectedRedirectError) as excinfo:
        client.probe_session()
    assert "secret-cookie-value" not in str(excinfo.value)
