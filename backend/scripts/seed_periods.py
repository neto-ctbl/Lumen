from __future__ import annotations

import argparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import SessionLocal
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization


def resolve_organization(session: Session, org_slug: str | None) -> Organization:
    if org_slug:
        organization = session.execute(select(Organization).where(Organization.slug == org_slug)).scalar_one_or_none()
        if organization is None:
            raise SystemExit(f"Organization with slug '{org_slug}' was not found.")
        if not organization.is_active:
            raise SystemExit(f"Organization with slug '{org_slug}' is inactive.")
        return organization

    settings = get_settings()
    if settings.app_env not in {"local", "development", "dev", "test"}:
        raise SystemExit("--org-slug is required outside local/MVP environments.")

    organizations = list(
        session.execute(
            select(Organization).where(Organization.is_active.is_(True)).order_by(Organization.id.asc())
        ).scalars()
    )
    if not organizations:
        raise SystemExit("No active organization found. Create one first or pass --org-slug.")
    if len(organizations) > 1:
        raise SystemExit("Multiple active organizations found. Pass --org-slug explicitly.")
    print(f"Warning: using the only active organization '{organizations[0].slug}' for period seed.")
    return organizations[0]


def seed_periods(session: Session, year: int, org_slug: str | None = None) -> tuple[int, int, int]:
    organization = resolve_organization(session, org_slug)
    created = 0
    updated = 0
    existing = {
        period.competencia: period
        for period in session.execute(
            select(FiscalPeriod).where(FiscalPeriod.organization_id == organization.id)
        ).scalars()
    }

    for month in range(1, 13):
        competencia = f"{year:04d}-{month:02d}"
        period = existing.get(competencia)
        if period is None:
            session.add(
                FiscalPeriod(
                    organization_id=organization.id,
                    year=year,
                    month=month,
                    competencia=competencia,
                    status="OPEN",
                )
            )
            created += 1
            continue

        changed = False
        if period.year != year:
            period.year = year
            changed = True
        if period.month != month:
            period.month = month
            changed = True
        if period.status != "OPEN":
            period.status = "OPEN"
            changed = True
        if changed:
            updated += 1

    session.commit()
    total = session.scalar(
        select(func.count()).select_from(FiscalPeriod).where(FiscalPeriod.organization_id == organization.id)
    )
    return created, updated, int(total or 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed fiscal periods for one year.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--org-slug", type=str, required=False)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    session = SessionLocal()
    try:
        created, updated, total = seed_periods(session, year=args.year, org_slug=args.org_slug)
        print(f"Seed completed. created={created} updated={updated} total={total}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
