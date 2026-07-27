from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.services.company_cnae_catalog import sync_organization_cnae_catalog  # noqa: E402
from backend.app.services.integrations.econtrole.sync import resolve_target_organization  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill company_cnaes from external_companies.")
    parser.add_argument("--org-slug", type=str, required=False)
    parser.add_argument("--company-id", type=int, required=False)
    parser.add_argument("--limit", type=int, required=False)
    parser.add_argument("--only-active", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_backfill(
    session: Session,
    *,
    org_slug: str | None = None,
    company_id: int | None = None,
    limit: int | None = None,
    only_active: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    organization = resolve_target_organization(session, org_slug)
    results = sync_organization_cnae_catalog(
        session,
        organization_id=organization.id,
        company_id=company_id,
        only_active=only_active,
        limit=limit,
        dry_run=dry_run,
    )
    summary = {
        "companies_received": len(results),
        "companies_processed": len(results),
        "companies_failed": 0,
        "cnaes_received": sum(item.cnaes_received for item in results),
        "cnaes_valid": sum(item.cnaes_valid for item in results),
        "cnaes_invalid": sum(item.cnaes_invalid for item in results),
        "created": sum(item.created for item in results),
        "updated": sum(item.updated for item in results),
        "reactivated": sum(item.reactivated for item in results),
        "deactivated": sum(item.deactivated for item in results),
        "unchanged": sum(item.unchanged for item in results),
    }
    if dry_run:
        session.rollback()
    else:
        session.commit()
    return summary


def main() -> None:
    args = build_parser().parse_args()
    session = SessionLocal()
    try:
        summary = run_backfill(
            session,
            org_slug=args.org_slug,
            company_id=args.company_id,
            limit=args.limit,
            only_active=args.only_active,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        session.rollback()
        raise SystemExit(str(exc)) from exc
    finally:
        session.close()
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
