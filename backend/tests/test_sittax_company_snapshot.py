from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


def test_sittax_company_snapshot_table_shape(db_session) -> None:
    inspector = inspect(db_session.get_bind())

    assert "sittax_company_snapshots" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("sittax_company_snapshots")}
    unique_constraints = inspector.get_unique_constraints("sittax_company_snapshots")
    indexes = inspector.get_indexes("sittax_company_snapshots")
    foreign_keys = inspector.get_foreign_keys("sittax_company_snapshots")

    assert columns["organization_id"]["nullable"] is False
    assert columns["sittax_company_id"]["nullable"] is False
    assert columns["cnpj"]["nullable"] is False
    assert columns["state_registration"]["nullable"] is True
    assert isinstance(columns["raw_payload"]["type"], JSONB)

    assert any(
        constraint["name"] == "uq_sittax_company_snapshots_org_company"
        and constraint["column_names"] == ["organization_id", "sittax_company_id"]
        for constraint in unique_constraints
    )
    assert any(
        index["name"] == "ix_sittax_company_snapshots_org_cnpj"
        and index["column_names"] == ["organization_id", "cnpj"]
        for index in indexes
    )
    assert any(
        fk["referred_table"] == "organizations" and fk["constrained_columns"] == ["organization_id"] for fk in foreign_keys
    )
    assert any(
        fk["referred_table"] == "external_companies" and fk["constrained_columns"] == ["company_id"] for fk in foreign_keys
    )
