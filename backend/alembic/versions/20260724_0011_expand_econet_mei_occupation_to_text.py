from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260724_0011"
down_revision = "20260722_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "econet_cnae_cache",
        "mei_occupation",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "econet_cnae_cache",
        "mei_occupation",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
