from __future__ import annotations

from sqlalchemy import select

from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.company_cnae_catalog import get_active_company_cnaes, sync_company_cnae_catalog


def _company(db_session, *, active: bool = True, primary: str | None = "8630-5/03", secondaries=None) -> ExternalCompany:
    organization = Organization(name="Org Catalog", slug=f"org-catalog-{db_session.query(Organization).count()+1}")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=f"{organization.id:014d}",
        razao_social="Empresa Catalogo",
        active=active,
        cnae_principal=primary,
        cnaes_secundarios=["8650-0/01", "8650-0/02"] if secondaries is None else secondaries,
    )
    db_session.add(company)
    db_session.flush()
    return company


def test_catalog_collects_primary_cnae(db_session) -> None:
    company = _company(db_session, secondaries=[])
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.cnaes_valid == 1
    assert result.created == 1


def test_catalog_collects_secondary_cnaes(db_session) -> None:
    company = _company(db_session, primary=None)
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.cnaes_valid == 2


def test_catalog_deduplicates_cnaes(db_session) -> None:
    company = _company(db_session, secondaries=["8650-0/01", "8650001"])
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.cnaes_valid == 2
    assert len(get_active_company_cnaes(db_session, company_id=company.id)) == 2


def test_primary_wins_over_secondary(db_session) -> None:
    company = _company(db_session, primary="8630-5/03", secondaries=["8630503"])
    sync_company_cnae_catalog(db_session, company=company)
    active = get_active_company_cnaes(db_session, company_id=company.id)
    assert len(active) == 1
    assert active[0].is_primary is True


def test_catalog_creates_new_rows(db_session) -> None:
    company = _company(db_session)
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.created == 3


def test_catalog_is_idempotent(db_session) -> None:
    company = _company(db_session)
    sync_company_cnae_catalog(db_session, company=company)
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.unchanged == 3


def test_catalog_reactivates_cnae(db_session) -> None:
    company = _company(db_session)
    sync_company_cnae_catalog(db_session, company=company)
    company.active = False
    sync_company_cnae_catalog(db_session, company=company)
    company.active = True
    company.cnaes_secundarios = ["8650-0/01"]
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.reactivated == 2


def test_catalog_deactivates_removed_cnae(db_session) -> None:
    company = _company(db_session)
    sync_company_cnae_catalog(db_session, company=company)
    company.cnaes_secundarios = []
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.deactivated == 2


def test_inactive_company_deactivates_catalog(db_session) -> None:
    company = _company(db_session)
    sync_company_cnae_catalog(db_session, company=company)
    company.active = False
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.deactivated == 3
    assert get_active_company_cnaes(db_session, company_id=company.id) == []


def test_invalid_cnae_does_not_abort_company(db_session) -> None:
    company = _company(db_session, secondaries=["invalido", "8650-0/01"])
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.cnaes_invalid == 1
    assert result.created == 2


def test_placeholder_zero_cnae_is_treated_as_invalid(db_session) -> None:
    company = _company(db_session, primary="0000-0/00", secondaries=["8650-0/01"])
    result = sync_company_cnae_catalog(db_session, company=company)
    assert result.cnaes_invalid == 1
    assert result.cnaes_valid == 1
    active = get_active_company_cnaes(db_session, company_id=company.id)
    assert [item.cnae for item in active] == ["8650001"]


def test_catalog_dry_run_does_not_write(db_session) -> None:
    company = _company(db_session)
    result = sync_company_cnae_catalog(db_session, company=company, dry_run=True)
    assert result.created == 3
    assert db_session.scalars(select(CompanyCnae).where(CompanyCnae.company_id == company.id)).all() == []
