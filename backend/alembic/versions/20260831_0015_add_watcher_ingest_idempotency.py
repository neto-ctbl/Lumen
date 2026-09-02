"""add watcher ingest idempotency

Revision ID: 20260831_0015
Revises: 20260824_0014
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0015"
down_revision = "20260824_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("watcher_file_events", sa.Column("normalized_relative_path", sa.String(length=500), nullable=True))
    op.add_column("watcher_file_events", sa.Column("idempotency_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_watcher_file_events_idempotency_key", "watcher_file_events", ["idempotency_key"])

    op.add_column("fiscal_evidences", sa.Column("watcher_event_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_fiscal_evidences_watcher_event_id",
        "fiscal_evidences",
        "watcher_file_events",
        ["watcher_event_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_fiscal_evidences_watcher_event_id", "fiscal_evidences", ["watcher_event_id"])


def downgrade() -> None:
    op.drop_constraint("uq_fiscal_evidences_watcher_event_id", "fiscal_evidences", type_="unique")
    op.drop_constraint("fk_fiscal_evidences_watcher_event_id", "fiscal_evidences", type_="foreignkey")
    op.drop_column("fiscal_evidences", "watcher_event_id")

    op.drop_constraint("uq_watcher_file_events_idempotency_key", "watcher_file_events", type_="unique")
    op.drop_column("watcher_file_events", "idempotency_key")
    op.drop_column("watcher_file_events", "normalized_relative_path")
