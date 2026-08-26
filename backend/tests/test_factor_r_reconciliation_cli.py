from __future__ import annotations

from backend.scripts import reconcile_factor_r as cli


def test_cli_parser_accepts_operational_arguments() -> None:
    args = cli.build_parser().parse_args(
        ["--organization-slug", "org", "--period", "2026-07", "--company-id", "12", "--dry-run", "--json"]
    )
    assert args.organization_slug == "org"
    assert args.period == "2026-07"
    assert args.company_id == 12
    assert args.dry_run is True
    assert args.json is True
