from __future__ import annotations

from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.econet.activity_classifier import (
    CLASSIFIER_SOURCE,
    classify_company_activity_types,
    post_process_company_activity_types,
    resolve_catalog_activity_type,
)


def _seed_company(db_session, *, cnaes: list[str]) -> ExternalCompany:
    organization = Organization(name="Org Activity", slug=f"org-activity-{db_session.query(Organization).count()+1}")
    db_session.add(organization)
    db_session.flush()
    company = ExternalCompany(
        organization_id=organization.id,
        cnpj=f"{organization.id:014d}",
        razao_social="Empresa Activity Types",
        active=True,
    )
    db_session.add(company)
    db_session.flush()
    for index, cnae in enumerate(cnaes):
        db_session.add(
            CompanyCnae(
                company_id=company.id,
                cnae=cnae,
                cnae_formatted=f"{cnae[:4]}-{cnae[4]}/{cnae[5:]}",
                is_primary=index == 0,
                source="ECONTROLE",
                active=True,
                first_seen_at=company.created_at,
                last_seen_at=company.created_at,
                deactivated_at=None,
            )
        )
    db_session.flush()
    return company


def test_catalog_contains_known_override() -> None:
    classification = resolve_catalog_activity_type("5611205")
    assert classification is not None
    assert classification.activity_type == "COMERCIO"


def test_post_processing_removes_generic_services() -> None:
    result = post_process_company_activity_types({"SERVICOS", "SERVICOS_MEDICOS_ODONTOLOGICOS", "COMERCIO"})
    assert result == ("COMERCIO", "SERVICOS_MEDICOS_ODONTOLOGICOS")


def test_classify_company_activity_types_creates_rows_from_catalog(db_session) -> None:
    company = _seed_company(db_session, cnaes=["4711302", "5611205"])
    result = classify_company_activity_types(db_session, company_id=company.id)
    rows = db_session.query(CompanyActivityType).filter(CompanyActivityType.company_id == company.id).all()

    assert result["created"] == 1
    assert sorted(row.activity_type for row in rows) == ["COMERCIO"]
    assert all(row.source == CLASSIFIER_SOURCE for row in rows)


def test_classify_company_activity_types_keeps_industria_with_specific_service(db_session) -> None:
    company = _seed_company(db_session, cnaes=["1099604", "6470103"])
    result = classify_company_activity_types(db_session, company_id=company.id)
    rows = db_session.query(CompanyActivityType).filter(CompanyActivityType.company_id == company.id).all()

    assert result["created"] == 2
    assert sorted(row.activity_type for row in rows) == ["INDUSTRIA", "SERVICOS_IMOBILIARIOS"]


def test_classify_company_activity_types_deletes_stale_rows(db_session) -> None:
    company = _seed_company(db_session, cnaes=["7112000"])
    db_session.add(
        CompanyActivityType(
            company_id=company.id,
            activity_type="INDUSTRIA",
            source=CLASSIFIER_SOURCE,
            confidence=1.0,
        )
    )
    db_session.flush()

    result = classify_company_activity_types(db_session, company_id=company.id)
    rows = db_session.query(CompanyActivityType).filter(CompanyActivityType.company_id == company.id).all()

    assert result["created"] == 1
    assert result["deleted"] == 1
    assert [row.activity_type for row in rows] == ["SERVICOS"]
