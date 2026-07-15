from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core.config import Settings
from backend.app.services.integrations.sittax.errors import SittaxConfigurationError
from backend.scripts import check_sittax_connection


def test_connection_script_fixture_mode_is_safe(capsys) -> None:
    exit_code = check_sittax_connection.run_check(fixture=True)

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Sittax authentication: OK" in captured
    assert "Companies returned: 2" in captured
    assert "12345678000195" not in captured
    assert "example.invalid" not in captured
    assert "jwt-" not in captured.lower()


def test_connection_script_real_mode_requires_credentials(monkeypatch) -> None:
    monkeypatch.setattr(check_sittax_connection, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(SittaxConfigurationError):
        check_sittax_connection.run_check(fixture=False)


def test_connection_script_closes_session_on_error(monkeypatch) -> None:
    closed: list[bool] = []

    class FakeSession:
        def __init__(self) -> None:
            self.office_id = None

        def exclusive(self):
            class _Ctx:
                def __enter__(inner_self):
                    return self

                def __exit__(inner_self, exc_type, exc, tb):
                    return None

            return _Ctx()

        def close(self) -> None:
            closed.append(True)

    class FakeClient:
        def __init__(self, *, session):
            self.session = session

        def authenticate_with_settings(self, settings):
            raise SittaxConfigurationError("missing credentials")

    monkeypatch.setattr(check_sittax_connection, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(check_sittax_connection, "SittaxSession", type("X", (), {"from_settings": staticmethod(lambda settings: FakeSession())}))
    monkeypatch.setattr(check_sittax_connection, "SittaxClient", FakeClient)

    with pytest.raises(SittaxConfigurationError):
        check_sittax_connection.run_check(fixture=False)

    assert closed == [True]


def test_connection_script_fixture_can_use_custom_companies_fixture(capsys, tmp_path: Path) -> None:
    custom_fixture = tmp_path / "companies.json"
    custom_fixture.write_text('{"sucesso": true, "empresas": []}', encoding="utf-8")

    exit_code = check_sittax_connection.run_check(fixture=True, companies_fixture=str(custom_fixture))

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Companies returned: 0" in captured
