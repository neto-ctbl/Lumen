from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.integrations.sittax.sync import SittaxCompanySyncResult
from backend.scripts import sync_sittax_companies


FIXTURES_DIR = Path("backend/tests/fixtures/sittax")


def test_script_parser_supports_expected_arguments() -> None:
    parser = sync_sittax_companies.build_parser()

    args = parser.parse_args(["--org-slug", "org-a", "--dry-run", "--companies-fixture", str(FIXTURES_DIR / "companies_success.json")])

    assert args.org_slug == "org-a"
    assert args.dry_run is True
    assert args.companies_fixture.endswith("companies_success.json")


def test_script_returns_safe_json_output(monkeypatch, capsys) -> None:
    class FakeRun:
        id = 10

    def fake_sync(session, *, org_slug, dry_run, companies_fixture, client):
        del session, org_slug, dry_run, companies_fixture, client
        return SittaxCompanySyncResult(
            run=FakeRun(),
            summary={"companies_received": 2, "companies_valid": 2},
            errors=[{"scope": "company", "error": "SittaxResponseError"}],
            dry_run=False,
            fixture_mode=True,
            status="PARTIAL",
        )

    monkeypatch.setattr(sync_sittax_companies, "sync_sittax_companies", fake_sync)

    exit_code = sync_sittax_companies.run_sync(
        org_slug="org-a",
        dry_run=False,
        companies_fixture=str(FIXTURES_DIR / "companies_success.json"),
    )

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["status"] == "PARTIAL"
    assert "12345678000195" not in json.dumps(captured)


def test_script_raises_for_missing_organization(db_session, monkeypatch) -> None:
    monkeypatch.setattr(sync_sittax_companies, "SessionLocal", lambda: db_session)

    with pytest.raises(ValueError):
        sync_sittax_companies.run_sync(
            org_slug="missing-org",
            dry_run=True,
            companies_fixture=str(FIXTURES_DIR / "companies_success.json"),
        )


def test_script_closes_session(monkeypatch) -> None:
    closed: list[bool] = []

    class FakeSession:
        def close(self) -> None:
            closed.append(True)

    def fake_sync(session, *, org_slug, dry_run, companies_fixture, client):
        del session, org_slug, dry_run, companies_fixture, client
        return SittaxCompanySyncResult(
            run=None,
            summary={"companies_received": 0},
            errors=[],
            dry_run=True,
            fixture_mode=True,
            status="DRY_RUN",
        )

    monkeypatch.setattr(sync_sittax_companies, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(sync_sittax_companies, "sync_sittax_companies", fake_sync)

    exit_code = sync_sittax_companies.run_sync(
        org_slug="org-a",
        dry_run=True,
        companies_fixture=str(FIXTURES_DIR / "companies_success.json"),
    )

    assert exit_code == 0
    assert closed == [True]
