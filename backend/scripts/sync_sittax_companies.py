from __future__ import annotations

import argparse
import json

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.sittax.sync import build_fixture_sittax_client, sync_sittax_companies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Sittax companies into local snapshots.")
    parser.add_argument("--org-slug", type=str, required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--companies-fixture", type=str, required=False)
    return parser


def run_sync(*, org_slug: str | None, dry_run: bool, companies_fixture: str | None) -> int:
    session = SessionLocal()
    try:
        client = build_fixture_sittax_client(companies_fixture=companies_fixture) if companies_fixture else None
        result = sync_sittax_companies(
            session,
            org_slug=org_slug,
            dry_run=dry_run,
            companies_fixture=companies_fixture,
            client=client,
        )
        output = {
            "run_id": result.run.id if result.run is not None else None,
            "status": result.status,
            "dry_run": result.dry_run,
            "fixture_mode": result.fixture_mode,
            "summary": result.summary,
            "errors": result.errors,
        }
        print(json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True))
        return 1 if result.status == "FAILED" else 0
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(run_sync(org_slug=args.org_slug, dry_run=args.dry_run, companies_fixture=args.companies_fixture))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
