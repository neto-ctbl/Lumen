from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.app.core.config import Settings


PREVIOUS_REVISION = "20260911_0018"
TABLE = "fiscal_document_parser_runs"


def test_parser_runs_migration_round_trip_constraints_and_indexes(
    prepared_test_database: None,
    alembic_config: Config,
    test_settings: Settings,
) -> None:
    engine = create_engine(test_settings.test_database_url, future=True)
    command.downgrade(alembic_config, PREVIOUS_REVISION)
    try:
        assert TABLE not in inspect(engine).get_table_names()

        command.upgrade(alembic_config, "head")
        inspector = inspect(engine)
        assert TABLE in inspector.get_table_names()

        columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
        assert set(columns) == {
            "id",
            "organization_id",
            "fiscal_evidence_id",
            "parser_name",
            "parser_version",
            "document_family",
            "extraction_status",
            "confidence",
            "structured_payload",
            "warnings",
            "created_at",
        }
        assert not columns["organization_id"]["nullable"]
        assert not columns["fiscal_evidence_id"]["nullable"]

        unique_names = {constraint["name"] for constraint in inspector.get_unique_constraints(TABLE)}
        check_names = {constraint["name"] for constraint in inspector.get_check_constraints(TABLE)}
        foreign_keys = {constraint["name"]: constraint for constraint in inspector.get_foreign_keys(TABLE)}
        indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
        assert "uq_fiscal_doc_parser_runs_org_evidence_parser_version" in unique_names
        assert "ck_fiscal_doc_parser_runs_extraction_status" in check_names
        assert "ck_fiscal_doc_parser_runs_confidence" in check_names
        assert foreign_keys["fk_fiscal_doc_parser_runs_evidence_id"]["referred_table"] == "fiscal_evidences"
        assert foreign_keys["fk_fiscal_doc_parser_runs_organization_id"]["referred_table"] == "organizations"
        assert "ix_fiscal_doc_parser_runs_org_evidence" in indexes
        assert "ix_fiscal_doc_parser_runs_org_status" in indexes

        command.downgrade(alembic_config, PREVIOUS_REVISION)
        assert TABLE not in inspect(engine).get_table_names()
    finally:
        command.upgrade(alembic_config, "head")
        engine.dispose()
