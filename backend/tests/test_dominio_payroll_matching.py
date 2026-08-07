from __future__ import annotations

from types import SimpleNamespace

from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.dominio.contracts import DominioCnpjStatus
from backend.app.services.integrations.dominio.matching import match_dominio_company_by_cnpj


def _create_org(db_session, slug: str) -> Organization:
    organization = Organization(name=slug, slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _create_company(db_session, organization: Organization, *, cnpj: str, active: bool = True) -> ExternalCompany:
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=cnpj,
        razao_social=f"Empresa {cnpj}",
        active=active,
    )
    db_session.add(company)
    db_session.flush()
    return company


def test_matching_returns_exact_match_in_same_org(db_session) -> None:
    organization = _create_org(db_session, "org-match-a")
    company = _create_company(db_session, organization, cnpj="12345678000195")

    result = match_dominio_company_by_cnpj(
        db_session,
        organization=organization,
        company_cnpj="12345678000195",
        company_cnpj_status=DominioCnpjStatus.VALID,
    )

    assert result.external_company_id == company.id
    assert result.match_status == "MATCHED"


def test_matching_does_not_cross_organizations(db_session) -> None:
    target_org = _create_org(db_session, "org-match-b")
    other_org = _create_org(db_session, "org-match-c")
    _create_company(db_session, other_org, cnpj="12345678000195")

    result = match_dominio_company_by_cnpj(
        db_session,
        organization=target_org,
        company_cnpj="12345678000195",
        company_cnpj_status=DominioCnpjStatus.VALID,
    )

    assert result.external_company_id is None
    assert result.match_status == "UNMATCHED"


def test_matching_returns_invalid_and_missing_without_name_fallback(db_session) -> None:
    organization = _create_org(db_session, "org-match-d")

    invalid = match_dominio_company_by_cnpj(
        db_session,
        organization=organization,
        company_cnpj="123",
        company_cnpj_status=DominioCnpjStatus.INVALID,
    )
    missing = match_dominio_company_by_cnpj(
        db_session,
        organization=organization,
        company_cnpj=None,
        company_cnpj_status=DominioCnpjStatus.MISSING,
    )

    assert invalid.match_status == "INVALID_CNPJ"
    assert missing.match_status == "MISSING_CNPJ"


def test_matching_can_surface_ambiguous_branch(monkeypatch, db_session) -> None:
    organization = _create_org(db_session, "org-match-e")

    class FakeScalarResult:
        def all(self):
            return [
                SimpleNamespace(id=1, active=True),
                SimpleNamespace(id=2, active=True),
            ]

    monkeypatch.setattr(db_session, "scalars", lambda stmt: FakeScalarResult())

    result = match_dominio_company_by_cnpj(
        db_session,
        organization=organization,
        company_cnpj="12345678000195",
        company_cnpj_status=DominioCnpjStatus.VALID,
    )

    assert result.external_company_id is None
    assert result.match_status == "AMBIGUOUS"
