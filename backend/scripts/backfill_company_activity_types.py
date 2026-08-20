from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.models.external_company import ExternalCompany  # noqa: E402
from backend.app.services.integrations.econtrole.sync import resolve_target_organization  # noqa: E402
from backend.app.services.integrations.econet.activity_classifier import classify_company_activity_types  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill company_activity_types from active company_cnaes.")
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
    query = select(ExternalCompany).where(ExternalCompany.organization_id == organization.id)
    if company_id is not None:
        query = query.where(ExternalCompany.id == company_id)
    if only_active:
        query = query.where(ExternalCompany.active.is_(True))
    query = query.order_by(ExternalCompany.id.asc())
    if limit is not None:
        query = query.limit(limit)

    companies = session.scalars(query).all()
    summary = {
        "companies_received": len(companies),
        "companies_processed": len(companies),
        "created": 0,
        "deleted": 0,
        "unchanged": 0,
        "unmapped_cnaes": 0,
    }
    for company in companies:
        result = classify_company_activity_types(session, company_id=company.id, dry_run=dry_run)
        summary["created"] += result["created"]
        summary["deleted"] += result["deleted"]
        summary["unchanged"] += result["unchanged"]
        summary["unmapped_cnaes"] += result["unmapped_cnaes"]

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
