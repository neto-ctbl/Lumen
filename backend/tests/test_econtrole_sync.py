from __future__ import annotations

from sqlalchemy import select

from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.services.integrations.econtrole.sync import (
    delete_company_from_econtrole_payload,
    upsert_company_from_econtrole_payload,
)


def _create_org(db_session, slug: str = "org-econtrole") -> Organization:
    organization = Organization(name="Org eControle", slug=slug)
    db_session.add(organization)
    db_session.flush()
    return organization


def _payload(**overrides):
    payload = {
        "id": "123",
        "profile_id": "456",
        "cnpj": "19.163.109/0001-78",
        "razao_social": "AC SOARES LTDA",
        "nome_fantasia": "AC Soares",
        "apelido_pasta": "AC Soares",
        "situacao": "ATIVA",
        "inscricao_estadual": "",
        "inscricao_municipal": "12345",
        "municipio": "Anapolis",
        "uf": "GO",
        "cnae_principal": "8630-5/03",
        "cnaes_secundarios": ["8650-0/01"],
        "updated_at": "2026-07-07T10:00:00-03:00",
    }
    payload.update(overrides)
    return payload


def test_upsert_creates_company(db_session) -> None:
    organization = _create_org(db_session)

    result = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    assert result.created is True
    assert result.updated is True
    company = db_session.scalar(select(ExternalCompany).where(ExternalCompany.id == result.company.id))
    assert company is not None
    assert company.organization_id == organization.id
    assert company.cnpj == "19163109000178"
    assert company.sync_status == "SYNCED"
    assert company.active is True


def test_second_upsert_is_idempotent_and_does_not_duplicate(db_session) -> None:
    organization = _create_org(db_session)
    first = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    second = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    companies = db_session.scalars(select(ExternalCompany).where(ExternalCompany.organization_id == organization.id)).all()
    assert first.company.id == second.company.id
    assert len(companies) == 1
    assert second.created is False


def test_upsert_updates_changed_fields(db_session) -> None:
    organization = _create_org(db_session)
    upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    result = upsert_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload=_payload(nome_fantasia="AC Soares Filial", municipio="Goiania"),
    )

    assert result.created is False
    assert result.updated is True
    assert result.company.nome_fantasia == "AC Soares Filial"
    assert result.company.municipio == "Goiania"


def test_soft_delete_marks_company_inactive(db_session) -> None:
    organization = _create_org(db_session)
    created = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    result = delete_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload={"cnpj": "19.163.109/0001-78", "deleted_at": "2026-07-07T11:00:00-03:00"},
    )

    assert result.company.id == created.company.id
    assert result.deleted is True
    assert result.company.active is False
    assert result.company.sync_status == "DELETED_ECONTROLE"
    assert result.company.deleted_at_econtrole is not None


def test_repeated_delete_is_idempotent(db_session) -> None:
    organization = _create_org(db_session)
    upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())
    delete_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload={"cnpj": "19.163.109/0001-78"},
    )

    result = delete_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload={"id": "123"},
    )

    assert result.deleted is False
    assert result.company.sync_status == "DELETED_ECONTROLE"


def test_upsert_after_delete_reactivates_company(db_session) -> None:
    organization = _create_org(db_session)
    first = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())
    delete_company_from_econtrole_payload(
        db_session,
        organization=organization,
        payload={"cnpj": "19.163.109/0001-78"},
    )

    result = upsert_company_from_econtrole_payload(db_session, organization=organization, payload=_payload())

    assert result.company.id == first.company.id
    assert result.company.active is True
    assert result.company.deleted_at_econtrole is None
    assert result.company.sync_status == "SYNCED"
