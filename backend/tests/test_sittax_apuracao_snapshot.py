from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


def test_sittax_apuracao_snapshot_table_shape(db_session) -> None:
    inspector = inspect(db_session.get_bind())

    assert "sittax_apuracao_snapshots" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("sittax_apuracao_snapshots")}
    unique_constraints = inspector.get_unique_constraints("sittax_apuracao_snapshots")
    indexes = inspector.get_indexes("sittax_apuracao_snapshots")
    foreign_keys = inspector.get_foreign_keys("sittax_apuracao_snapshots")

    assert columns["organization_id"]["nullable"] is False
    assert columns["sittax_company_snapshot_id"]["nullable"] is False
    assert columns["fiscal_period_id"]["nullable"] is False
    assert columns["external_company_id"]["nullable"] is True
    assert columns["company_name"]["nullable"] is True
    assert columns["is_transmitted"]["nullable"] is True
    assert isinstance(columns["raw_payload"]["type"], JSONB)

    assert any(
        constraint["name"] == "uq_sittax_apuracao_snapshots_org_company_period"
        and constraint["column_names"] == ["organization_id", "sittax_company_snapshot_id", "fiscal_period_id"]
        for constraint in unique_constraints
    )
    assert any(
        index["name"] == "ix_sittax_apuracao_snapshots_org_period"
        and index["column_names"] == ["organization_id", "fiscal_period_id"]
        for index in indexes
    )
    assert any(
        fk["referred_table"] == "sittax_company_snapshots" and fk["constrained_columns"] == ["sittax_company_snapshot_id"]
        for fk in foreign_keys
    )
