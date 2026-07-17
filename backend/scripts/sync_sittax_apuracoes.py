from __future__ import annotations

import argparse
import json
import re
import sys

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.sittax.sync import build_fixture_sittax_client, sync_sittax_apuracoes

PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Sittax apuracoes into local snapshots.")
    parser.add_argument("--org-slug", type=str, required=False)
    parser.add_argument("--period", type=str, required=True)
    parser.add_argument("--company-id", type=int, required=False)
    parser.add_argument("--limit", type=int, required=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apuracao-fixture", type=str, required=False)
    return parser


def validate_period(period: str) -> None:
    if period != period.strip() or not PERIOD_RE.fullmatch(period):
        raise ValueError("Period must use YYYY-MM format.")
    month = int(period[5:7])
    if month < 1 or month > 12:
        raise ValueError("Period must contain a valid month.")


def run_sync(
    *,
    org_slug: str | None,
    period: str,
    company_id: int | None,
    limit: int | None,
    dry_run: bool,
    apuracao_fixture: str | None,
) -> int:
    validate_period(period)
    session = SessionLocal()
    try:
        if apuracao_fixture and not dry_run:
            print(
                "Warning: fixture mode with writes should be used only against a test database.",
                file=sys.stderr,
            )
        client = build_fixture_sittax_client(apuracao_fixture=apuracao_fixture) if apuracao_fixture else None
        result = sync_sittax_apuracoes(
            session,
            org_slug=org_slug,
            period=period,
            company_id=company_id,
            limit=limit,
            dry_run=dry_run,
            apuracao_fixture=apuracao_fixture,
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
        raise SystemExit(
            run_sync(
                org_slug=args.org_slug,
                period=args.period,
                company_id=args.company_id,
                limit=args.limit,
                dry_run=args.dry_run,
                apuracao_fixture=args.apuracao_fixture,
            )
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
