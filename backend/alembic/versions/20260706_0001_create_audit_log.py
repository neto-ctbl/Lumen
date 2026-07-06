from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260706_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=True),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_event_type"), "audit_log", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_event_type"), table_name="audit_log")
    op.drop_table("audit_log")
