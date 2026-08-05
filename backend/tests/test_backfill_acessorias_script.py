from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.scripts import backfill_acessorias


@dataclass
class _FakeResult:
    status: str
    dry_run: bool
    run_ids: list[int]
    summary: dict
    period_summaries: list[dict]
    errors: list[dict]


def test_build_parser_requires_main_arguments() -> None:
    parser = backfill_acessorias.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(
        [
            "--org-slug",
            "neto-contabilidade",
            "--from-period",
            "2026-01",
            "--to-period",
            "2026-07",
        ]
    )

    assert args.org_slug == "neto-contabilidade"
    assert args.from_period == "2026-01"
    assert args.to_period == "2026-07"
    assert args.only_active is True
    assert args.fiscal_only is False


def test_run_backfill_prints_structured_summary(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        backfill_acessorias,
        "backfill_acessorias",
        lambda *args, **kwargs: _FakeResult(
            status="SUCCESS",
            dry_run=True,
            run_ids=[11, 12],
            summary={"periods_requested": 2, "failures": 0},
            period_summaries=[{"period": "2026-01", "status": "SUCCESS"}],
            errors=[],
        ),
    )
    monkeypatch.setattr(backfill_acessorias, "build_fixture_acessorias_client", lambda **kwargs: None)

    exit_code = backfill_acessorias.run_backfill(
        org_slug="neto-contabilidade",
        from_period="2026-01",
        to_period="2026-02",
        company_id=None,
        dry_run=True,
        skip_companies=False,
        only_active=True,
        fiscal_only=False,
        stop_on_error=False,
        companies_fixture=None,
        deliveries_fixture=None,
        deliveries_fixture_dir=None,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "SUCCESS"' in captured.out
    assert '"periods_requested": 2' in captured.out


def test_run_backfill_returns_non_zero_for_global_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        backfill_acessorias,
        "backfill_acessorias",
        lambda *args, **kwargs: _FakeResult(
            status="FAILED",
            dry_run=False,
            run_ids=[],
            summary={"periods_failed": 1, "failures": 1},
            period_summaries=[],
            errors=[{"scope": "period", "period": "2026-01", "error": "failure"}],
        ),
    )
    monkeypatch.setattr(backfill_acessorias, "build_fixture_acessorias_client", lambda **kwargs: None)

    exit_code = backfill_acessorias.run_backfill(
        org_slug="neto-contabilidade",
        from_period="2026-01",
        to_period="2026-01",
        company_id=None,
        dry_run=False,
        skip_companies=False,
        only_active=True,
        fiscal_only=False,
        stop_on_error=False,
        companies_fixture=None,
        deliveries_fixture=None,
        deliveries_fixture_dir=None,
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"periods_failed": 1' in captured.out


def test_main_surfaces_invalid_org_error(monkeypatch) -> None:
    monkeypatch.setattr(
        backfill_acessorias,
        "run_backfill",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Organization with slug 'missing' was not found.")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "backfill_acessorias",
            "--org-slug",
            "missing",
            "--from-period",
            "2026-01",
            "--to-period",
            "2026-01",
        ],
    )

    with pytest.raises(SystemExit, match="Organization with slug 'missing' was not found."):
        backfill_acessorias.main()


def test_main_surfaces_foreign_company_rejection(monkeypatch) -> None:
    monkeypatch.setattr(
        backfill_acessorias,
        "run_backfill",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Company '99' was not found for organization 'org'.")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "backfill_acessorias",
            "--org-slug",
            "org",
            "--from-period",
            "2026-01",
            "--to-period",
            "2026-01",
            "--company-id",
            "99",
        ],
    )

    with pytest.raises(SystemExit, match="Company '99' was not found for organization 'org'."):
        backfill_acessorias.main()
