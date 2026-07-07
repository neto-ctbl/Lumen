from __future__ import annotations

import pytest
from sqlalchemy import func, select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_period import FiscalPeriod
from backend.app.models.organization import Organization
from backend.scripts.seed_periods import seed_periods


def test_seed_periods_creates_12_competencias_idempotently(db_session) -> None:
    organization = Organization(name="Neto Contabilidade", slug="neto-contabilidade")
    db_session.add(organization)
    db_session.flush()

    created, updated, total = seed_periods(db_session, year=2026, org_slug="neto-contabilidade")
    assert created == 12
    assert updated == 0
    assert total == 12

    created, updated, total = seed_periods(db_session, year=2026, org_slug="neto-contabilidade")
    assert created == 0
    assert updated == 0
    assert total == 12

    periods = list(
        db_session.execute(
            select(FiscalPeriod)
            .where(FiscalPeriod.organization_id == organization.id)
            .order_by(FiscalPeriod.competencia)
        ).scalars()
    )
    assert len(periods) == 12
    assert [period.competencia for period in periods] == [f"2026-{month:02d}" for month in range(1, 13)]
    assert all(len(period.competencia) == 7 and period.competencia[4] == "-" for period in periods)
    assert db_session.scalar(select(func.count()).select_from(ExternalCompany)) == 0
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == 0


def test_seed_periods_requires_org_slug_when_multiple_active_orgs(db_session) -> None:
    db_session.add_all(
        [
            Organization(name="Org A", slug="org-a"),
            Organization(name="Org B", slug="org-b"),
        ]
    )
    db_session.flush()

    with pytest.raises(SystemExit, match="Multiple active organizations found. Pass --org-slug explicitly."):
        seed_periods(db_session, year=2026)

    assert db_session.scalar(select(func.count()).select_from(ExternalCompany)) == 0
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == 0
