from __future__ import annotations

import argparse
import json

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.acessorias.sync import FixtureAcessoriasClient, sync_acessorias_period


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Acessorias companies and deliveries into Lumen.")
    parser.add_argument("--org-slug", type=str, required=False)
    parser.add_argument("--period", type=str, required=True)
    parser.add_argument("--company-id", type=int, required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-companies", action="store_true")
    parser.add_argument("--skip-deliveries", action="store_true")
    parser.add_argument("--companies-fixture", type=str, required=False)
    parser.add_argument("--deliveries-fixture", type=str, required=False)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    fixture_mode = bool(args.companies_fixture or args.deliveries_fixture)
    if fixture_mode and not (args.companies_fixture and args.deliveries_fixture):
        raise SystemExit("Both --companies-fixture and --deliveries-fixture are required in fixture mode.")

    session = SessionLocal()
    try:
        client = None
        if fixture_mode:
            client = FixtureAcessoriasClient.from_files(
                companies_path=args.companies_fixture,
                deliveries_path=args.deliveries_fixture,
            )
        result = sync_acessorias_period(
            session,
            period=args.period,
            org_slug=args.org_slug,
            company_id=args.company_id,
            dry_run=args.dry_run,
            sync_companies=not args.skip_companies,
            sync_deliveries=not args.skip_deliveries,
            client=client,
        )
        output = {
            "run_id": result.run.id if result.run is not None else None,
            "status": result.run.status if result.run is not None else "DRY_RUN",
            "dry_run": result.dry_run,
            "summary": result.summary,
            "errors": result.errors,
        }
        print(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True))
        if result.run is not None and result.run.status == "FAILED":
            raise SystemExit(1)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        session.close()


if __name__ == "__main__":
    main()
