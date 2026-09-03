"""create watcher agent health

Revision ID: 20260902_0016
Revises: 20260831_0015
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260902_0016"
down_revision = "20260831_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watcher_agent_health",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.BigInteger(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("reported_status", sa.String(length=20), nullable=False),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("agent_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_last_successful_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", name="uq_watcher_agent_health_organization"),
    )
    op.create_index("ix_watcher_agent_health_organization_id", "watcher_agent_health", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_watcher_agent_health_organization_id", table_name="watcher_agent_health")
    op.drop_table("watcher_agent_health")
