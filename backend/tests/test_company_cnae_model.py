from __future__ import annotations

from sqlalchemy import inspect

from backend.app.models import CompanyCnae


def test_company_cnae_table_registered(prepared_test_database: None, test_settings) -> None:
    inspector = inspect(__import__("sqlalchemy").create_engine(test_settings.test_database_url, future=True))
    assert "company_cnaes" in inspector.get_table_names()


def test_company_cnae_unique_company_and_cnae(db_session) -> None:
    inspector = inspect(db_session.bind)
    uniques = inspector.get_unique_constraints("company_cnaes")
    assert any(item["name"] == "uq_company_cnaes_company_cnae" for item in uniques)


def test_company_cnae_requires_seven_digits(db_session) -> None:
    checks = inspect(db_session.bind).get_check_constraints("company_cnaes")
    assert any(item["name"] == "ck_company_cnaes_cnae_digits" for item in checks)


def test_company_cnae_indexes(db_session) -> None:
    indexes = inspect(db_session.bind).get_indexes("company_cnaes")
    names = {item["name"] for item in indexes}
    assert "ix_company_cnaes_company_id" in names
    assert "ix_company_cnaes_cnae" in names
    assert "ix_company_cnaes_company_active" in names
    assert "ix_company_cnaes_cnae_active" in names


def test_company_cnae_foreign_key(db_session) -> None:
    fks = inspect(db_session.bind).get_foreign_keys("company_cnaes")
    assert any(item["referred_table"] == "external_companies" for item in fks)
    assert CompanyCnae.__tablename__ == "company_cnaes"
