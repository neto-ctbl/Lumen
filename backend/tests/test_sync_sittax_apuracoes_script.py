from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.integrations.sittax.sync import SittaxApuracaoSyncResult
from backend.scripts import sync_sittax_apuracoes


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def test_script_parser_supports_expected_arguments() -> None:
    parser = sync_sittax_apuracoes.build_parser()

    args = parser.parse_args(
        [
            "--org-slug",
            "org-a",
            "--period",
            "2026-06",
            "--company-id",
            "10",
            "--limit",
            "5",
            "--dry-run",
            "--apuracao-fixture",
            str(FIXTURES_DIR / "apuracao_success.json"),
        ]
    )

    assert args.org_slug == "org-a"
    assert args.period == "2026-06"
    assert args.company_id == 10
    assert args.limit == 5
    assert args.dry_run is True


def test_script_returns_safe_json_output(monkeypatch, capsys) -> None:
    class FakeRun:
        id = 10

    def fake_sync(session, *, org_slug, period, company_id, limit, dry_run, apuracao_fixture, client):
        del session, org_slug, period, company_id, limit, dry_run, apuracao_fixture, client
        return SittaxApuracaoSyncResult(
            run=FakeRun(),
            summary={"companies_selected": 1, "snapshots_created": 1},
            errors=[{"scope": "company", "error": "SittaxResponseError"}],
            dry_run=False,
            fixture_mode=True,
            status="SUCCESS",
        )

    monkeypatch.setattr(sync_sittax_apuracoes, "sync_sittax_apuracoes", fake_sync)

    exit_code = sync_sittax_apuracoes.run_sync(
        org_slug="org-a",
        period="2026-06",
        company_id=1,
        limit=1,
        dry_run=False,
        apuracao_fixture=str(FIXTURES_DIR / "apuracao_success.json"),
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "12345678000195" not in json.dumps(captured)


def test_script_rejects_invalid_period(monkeypatch) -> None:
    monkeypatch.setattr(sync_sittax_apuracoes, "SessionLocal", lambda: type("FakeSession", (), {"close": lambda self: None})())

    with pytest.raises(ValueError):
        sync_sittax_apuracoes.run_sync(
            org_slug="org-a",
            period="06/2026",
            company_id=None,
            limit=None,
            dry_run=True,
            apuracao_fixture=str(FIXTURES_DIR / "apuracao_success.json"),
        )
