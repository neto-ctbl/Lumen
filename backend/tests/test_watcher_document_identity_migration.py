from __future__ import annotations

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from backend.app.core.config import Settings


PREVIOUS_REVISION = "20260904_0017"


def test_migration_backfills_existing_relation_and_round_trips(
    prepared_test_database: None,
    alembic_config: Config,
    test_settings: Settings,
) -> None:
    engine = create_engine(test_settings.test_database_url, future=True)
    command.downgrade(alembic_config, PREVIOUS_REVISION)
    try:
        with engine.begin() as connection:
            organization_id = connection.execute(
                text(
                    "INSERT INTO organizations (name, slug) "
                    "VALUES ('Synthetic Migration Org', 'watcher-migration-roundtrip') RETURNING id"
                )
            ).scalar_one()
            event_id = connection.execute(
                text(
                    """
                    INSERT INTO watcher_file_events
                        (organization_id, event_type, file_path, file_name, file_hash, status)
                    VALUES
                        (:organization_id, 'FILE_STABLE', 'synthetic\\document.pdf',
                         'document.pdf', :file_hash, 'PENDING')
                    RETURNING id
                    """
                ),
                {"organization_id": organization_id, "file_hash": "a" * 64},
            ).scalar_one()
            evidence_id = connection.execute(
                text(
                    """
                    INSERT INTO fiscal_evidences
                        (organization_id, watcher_event_id, source, source_type, file_hash, status)
                    VALUES
                        (:organization_id, :event_id, 'WATCHER_FILE', 'WATCHER_INGEST',
                         :file_hash, 'PENDENTE')
                    RETURNING id
                    """
                ),
                {"organization_id": organization_id, "event_id": event_id, "file_hash": "a" * 64},
            ).scalar_one()

        command.upgrade(alembic_config, "head")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT evidence_id FROM watcher_file_events WHERE id = :event_id"),
                {"event_id": event_id},
            ).scalar_one() == evidence_id

        command.downgrade(alembic_config, PREVIOUS_REVISION)
        assert "evidence_id" not in {column["name"] for column in inspect(engine).get_columns("watcher_file_events")}
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT watcher_event_id FROM fiscal_evidences WHERE id = :evidence_id"),
                {"evidence_id": evidence_id},
            ).scalar_one() == event_id

        command.upgrade(alembic_config, "head")
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE watcher_file_events SET evidence_id = NULL WHERE id = :event_id"),
                {"event_id": event_id},
            )
            connection.execute(text("DELETE FROM fiscal_evidences WHERE id = :evidence_id"), {"evidence_id": evidence_id})
            connection.execute(text("DELETE FROM watcher_file_events WHERE id = :event_id"), {"event_id": event_id})
            connection.execute(text("DELETE FROM organizations WHERE id = :organization_id"), {"organization_id": organization_id})
    finally:
        command.upgrade(alembic_config, "head")
        engine.dispose()


def test_migration_refuses_duplicate_watcher_identities_without_merging(
    prepared_test_database: None,
    alembic_config: Config,
    test_settings: Settings,
) -> None:
    engine = create_engine(test_settings.test_database_url, future=True)
    command.downgrade(alembic_config, PREVIOUS_REVISION)
    try:
        with engine.begin() as connection:
            organization_id = connection.execute(
                text(
                    "INSERT INTO organizations (name, slug) "
                    "VALUES ('Synthetic Duplicate Org', 'watcher-migration-duplicates') RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO fiscal_evidences
                        (organization_id, source, source_type, file_hash, status)
                    VALUES
                        (:organization_id, 'WATCHER_FILE', 'WATCHER_INGEST', :file_hash, 'PENDENTE'),
                        (:organization_id, 'WATCHER_FILE', 'WATCHER_INGEST', :file_hash, 'PENDENTE')
                    """
                ),
                {"organization_id": organization_id, "file_hash": "b" * 64},
            )

        with pytest.raises(RuntimeError, match="2 duplicate organization/hash group|1 duplicate organization/hash group"):
            command.upgrade(alembic_config, "head")

        with engine.begin() as connection:
            assert connection.execute(
                text(
                    "SELECT count(*) FROM fiscal_evidences "
                    "WHERE organization_id = :organization_id AND source = 'WATCHER_FILE'"
                ),
                {"organization_id": organization_id},
            ).scalar_one() == 2
            connection.execute(
                text("DELETE FROM fiscal_evidences WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            connection.execute(text("DELETE FROM organizations WHERE id = :organization_id"), {"organization_id": organization_id})
    finally:
        command.upgrade(alembic_config, "head")
        engine.dispose()
