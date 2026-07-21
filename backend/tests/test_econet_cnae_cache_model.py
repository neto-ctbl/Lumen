from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.models import EconetCnaeCache


def test_econet_cnae_cache_registered_in_model_package() -> None:
    assert EconetCnaeCache.__tablename__ == "econet_cnae_cache"


def test_econet_cnae_cache_table_shape(db_session) -> None:
    inspector = inspect(db_session.get_bind())
    assert "econet_cnae_cache" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("econet_cnae_cache")}
    unique_constraints = inspector.get_unique_constraints("econet_cnae_cache")
    indexes = inspector.get_indexes("econet_cnae_cache")
    check_constraints = inspector.get_check_constraints("econet_cnae_cache")

    assert columns["cnae"]["nullable"] is False
    assert columns["description"]["nullable"] is False
    assert columns["econet_id_cnae"]["nullable"] is False
    assert columns["retrieved_at"]["nullable"] is False
    assert columns["expires_at"]["nullable"] is False
    assert isinstance(columns["activity_types"]["type"], JSONB)
    assert isinstance(columns["normalized_payload"]["type"], JSONB)
    assert str(columns["presumed_profit_irpj_rate"]["type"]) == "NUMERIC(5, 2)"
    assert str(columns["factor_r_threshold"]["type"]) == "NUMERIC(5, 2)"

    assert any(
        constraint["name"] == "uq_econet_cnae_cache_cnae" and constraint["column_names"] == ["cnae"]
        for constraint in unique_constraints
    )
    assert any(index["name"] == "ix_econet_cnae_cache_econet_id_cnae" for index in indexes)
    assert any(index["name"] == "ix_econet_cnae_cache_expires_at" for index in indexes)
    assert any(constraint["name"] == "ck_econet_cnae_cache_cnae_digits" for constraint in check_constraints)
    assert any(constraint["name"] == "ck_econet_cnae_cache_parse_status" for constraint in check_constraints)
