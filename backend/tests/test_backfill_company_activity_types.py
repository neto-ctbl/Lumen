from __future__ import annotations

import subprocess
import sys

from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.scripts.backfill_company_activity_types import run_backfill


def _seed_company(db_session, *, slug: str = "org-backfill", cnae: str = "4711302") -> tuple[Organization, ExternalCompany]:
    organization = Organization(name="Org Backfill Activity", slug=slug)
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj="11111111000111",
        razao_social="Empresa Backfill Activity",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    db_session.add(
        CompanyCnae(
            company_id=company.id,
            cnae=cnae,
            cnae_formatted=f"{cnae[:4]}-{cnae[4]}/{cnae[5:]}",
            is_primary=True,
            source="ECONTROLE",
            active=True,
            first_seen_at=company.created_at,
            last_seen_at=company.created_at,
            deactivated_at=None,
        )
    )
    db_session.flush()
    return organization, company


def test_backfill_company_activity_types_dry_run(db_session) -> None:
    organization, _company = _seed_company(db_session)
    summary = run_backfill(db_session, org_slug=organization.slug, dry_run=True)
    assert summary["companies_processed"] == 1
    assert summary["created"] == 1
    assert db_session.query(CompanyActivityType).count() == 0


def test_backfill_company_activity_types_writes_rows(db_session) -> None:
    organization, company = _seed_company(db_session, slug="org-backfill-write", cnae="5611205")
    summary = run_backfill(db_session, org_slug=organization.slug, dry_run=False)
    rows = db_session.query(CompanyActivityType).filter(CompanyActivityType.company_id == company.id).all()
    assert summary["created"] == 1
    assert [row.activity_type for row in rows] == ["COMERCIO"]


def test_backfill_company_activity_types_help() -> None:
    result = subprocess.run(
        [sys.executable, "backend/scripts/backfill_company_activity_types.py", "--help"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode == 0
