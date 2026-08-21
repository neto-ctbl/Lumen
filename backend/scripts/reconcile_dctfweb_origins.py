from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.dctfweb_origins import reconcile_dctfweb_period
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile expected DCTFWeb origins from persisted Lumen evidence.")
    parser.add_argument("--organization-slug", required=True)
    parser.add_argument("--period", required=True, help="Assessment competence in YYYY-MM format.")
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def run_reconciliation(
    *, organization_slug: str, period: str, company_id: int | None, dry_run: bool, output_json: bool
) -> int:
    session = SessionLocal()
    try:
        organization = resolve_target_organization(session, organization_slug)
        summary = reconcile_dctfweb_period(
            session,
            organization,
            period,
            external_company_id=company_id,
            dry_run=dry_run,
        ).to_dict()
        if output_json:
            print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
        else:
            for key, value in summary.items():
                print(f"{key}={value}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(
        run_reconciliation(
            organization_slug=args.organization_slug,
            period=args.period,
            company_id=args.company_id,
            dry_run=args.dry_run,
            output_json=args.json,
        )
    )


if __name__ == "__main__":
    main()
