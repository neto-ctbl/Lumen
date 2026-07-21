from __future__ import annotations

from dataclasses import dataclass

from backend.scripts import sync_sittax_operational
from backend.app.services.integrations.sittax.sync import SittaxOperationalSyncSummary


@dataclass
class _FakeRun:
    id: int


@dataclass
class _FakeResult:
    run: _FakeRun | None
    status: str
    dry_run: bool
    fixture_mode: bool
    summary: dict
    errors: list[dict]


def test_run_sync_prints_structured_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sync_sittax_operational,
        "sync_sittax_operational",
        lambda *args, **kwargs: _FakeResult(
            run=_FakeRun(id=7),
            status="SUCCESS",
            dry_run=True,
            fixture_mode=False,
            summary={"companies_processed": 1},
            errors=[],
        ),
    )

    exit_code = sync_sittax_operational.run_sync(
        org_slug="org",
        period="2026-06",
        company_id=1,
        limit=1,
        scope="ALL",
        max_pages=100,
        dry_run=True,
        diagnostic_contract=False,
        apuracao_fixture=None,
        difal_fixture=None,
        entry_documents_fixture=None,
        exit_documents_fixture=None,
        tasks_fixture=None,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"run_id": 7' in captured.out
    assert '"status": "SUCCESS"' in captured.out


def test_operational_summary_to_dict_supports_slots_dataclass() -> None:
    summary = SittaxOperationalSyncSummary(companies_processed=1, failures=0)

    payload = summary.to_dict()

    assert payload["companies_processed"] == 1
    assert payload["failures"] == 0
