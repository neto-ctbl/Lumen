from __future__ import annotations

import argparse
import json
import sys

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.acessorias.backfill import (
    backfill_acessorias,
    build_fixture_acessorias_client,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the retroactive Acessorias operational backfill.")
    parser.add_argument("--org-slug", type=str, required=True)
    parser.add_argument("--from-period", type=str, required=True)
    parser.add_argument("--to-period", type=str, required=True)
    parser.add_argument("--company-id", type=int, required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-companies", action="store_true")
    parser.add_argument("--only-active", action="store_true", default=True)
    parser.add_argument("--fiscal-only", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--companies-fixture", type=str, required=False)
    parser.add_argument("--deliveries-fixture", type=str, required=False)
    parser.add_argument("--deliveries-fixture-dir", type=str, required=False)
    return parser


def run_backfill(
    *,
    org_slug: str,
    from_period: str,
    to_period: str,
    company_id: int | None,
    dry_run: bool,
    skip_companies: bool,
    only_active: bool,
    fiscal_only: bool,
    stop_on_error: bool,
    companies_fixture: str | None,
    deliveries_fixture: str | None,
    deliveries_fixture_dir: str | None,
) -> int:
    session = SessionLocal()
    try:
        client = build_fixture_acessorias_client(
            companies_fixture=companies_fixture,
            deliveries_fixture=deliveries_fixture,
            deliveries_fixture_dir=deliveries_fixture_dir,
        )
        if client is not None and not dry_run:
            print("Warning: fixture mode with writes should be used only against a test database.", file=sys.stderr)

        result = backfill_acessorias(
            session,
            org_slug=org_slug,
            from_period=from_period,
            to_period=to_period,
            company_id=company_id,
            dry_run=dry_run,
            skip_companies=skip_companies,
            only_active=only_active,
            fiscal_only=fiscal_only,
            stop_on_error=stop_on_error,
            client=client,
        )
        print(
            json.dumps(
                {
                    "status": result.status,
                    "dry_run": result.dry_run,
                    "run_ids": result.run_ids,
                    "summary": result.summary,
                    "period_summaries": result.period_summaries,
                    "errors": result.errors,
                },
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if result.status == "FAILED" else 0
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(
            run_backfill(
                org_slug=args.org_slug,
                from_period=args.from_period,
                to_period=args.to_period,
                company_id=args.company_id,
                dry_run=args.dry_run,
                skip_companies=args.skip_companies,
                only_active=args.only_active,
                fiscal_only=args.fiscal_only,
                stop_on_error=args.stop_on_error,
                companies_fixture=args.companies_fixture,
                deliveries_fixture=args.deliveries_fixture,
                deliveries_fixture_dir=args.deliveries_fixture_dir,
            )
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
