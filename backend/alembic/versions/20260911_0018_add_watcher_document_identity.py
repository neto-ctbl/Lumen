"""add watcher document identity

Revision ID: 20260911_0018
Revises: 20260904_0017
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260911_0018"
down_revision = "20260904_0017"
branch_labels = None
depends_on = None


WATCHER_IDENTITY_INDEX = "uq_fiscal_evidences_watcher_org_source_hash"


def upgrade() -> None:
    connection = op.get_bind()
    duplicate_groups = connection.execute(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT organization_id, file_hash
                FROM fiscal_evidences
                WHERE source = 'WATCHER_FILE' AND file_hash IS NOT NULL
                GROUP BY organization_id, file_hash
                HAVING count(*) > 1
            ) AS duplicates
            """
        )
    ).scalar_one()
    if duplicate_groups:
        raise RuntimeError(
            "Cannot add watcher document identity: "
            f"{duplicate_groups} duplicate organization/hash group(s) require explicit review."
        )

    op.add_column("watcher_file_events", sa.Column("evidence_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_watcher_file_events_evidence_id",
        "watcher_file_events",
        "fiscal_evidences",
        ["evidence_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_watcher_file_events_evidence_id", "watcher_file_events", ["evidence_id"], unique=False)

    connection.execute(
        sa.text(
            """
            UPDATE watcher_file_events AS event
            SET evidence_id = evidence.id
            FROM fiscal_evidences AS evidence
            WHERE evidence.watcher_event_id = event.id
              AND evidence.source = 'WATCHER_FILE'
            """
        )
    )

    op.create_index(
        WATCHER_IDENTITY_INDEX,
        "fiscal_evidences",
        ["organization_id", "source", "file_hash"],
        unique=True,
        postgresql_where=sa.text("source = 'WATCHER_FILE' AND file_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(WATCHER_IDENTITY_INDEX, table_name="fiscal_evidences")
    op.drop_index("ix_watcher_file_events_evidence_id", table_name="watcher_file_events")
    op.drop_constraint("fk_watcher_file_events_evidence_id", "watcher_file_events", type_="foreignkey")
    op.drop_column("watcher_file_events", "evidence_id")
