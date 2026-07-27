from __future__ import annotations

import httpx

from backend.app.core.config import Settings
from backend.app.services.integrations.econet.assisted_session import get_econet_assisted_session, reset_econet_assisted_session
from backend.app.services.integrations.econet.client import EconetClient
from backend.app.services.integrations.econet.errors import EconetUnexpectedRedirectError


def test_snapshot_and_errors_do_not_expose_secrets() -> None:
    reset_econet_assisted_session()
    settings = Settings(
        database_url="postgresql+psycopg://lumen:lumen@localhost:5435/lumen",
        test_database_url="postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test",
        econet_assisted_session_enabled=True,
    )
    session = get_econet_assisted_session(settings)
    session.import_storage_state(
        {
            "cookies": [
                {"name": "PHPSESSID", "value": "PHPSESSID=secret", "domain": ".econeteditora.com.br", "path": "/"}
            ]
        }
    )
    snapshot_text = repr(session.snapshot())
    assert "PHPSESSID=secret" not in snapshot_text
    assert "Bearer" not in snapshot_text
    assert "localStorage" not in snapshot_text
    assert "token" not in snapshot_text.lower()

    client = EconetClient(
        settings=settings,
        http_client=httpx.Client(
            base_url=settings.econet_base_url,
            transport=httpx.MockTransport(
                lambda request: httpx.Response(302, headers={"location": "https://example.com/login"})
            ),
        ),
    )
    try:
        client.probe_session()
    except EconetUnexpectedRedirectError as exc:
        text = str(exc)
        assert "Cookie:" not in text
        assert "PHPSESSID=" not in text
        assert "Bearer" not in text
        assert "localStorage" not in text
