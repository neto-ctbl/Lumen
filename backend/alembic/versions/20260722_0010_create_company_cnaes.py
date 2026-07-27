from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260722_0010"
down_revision = "20260721_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_cnaes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("cnae", sa.String(length=7), nullable=False),
        sa.Column("cnae_formatted", sa.String(length=10), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(cnae) = 7 AND cnae ~ '^[0-9]+$'", name="ck_company_cnaes_cnae_digits"),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "cnae", name="uq_company_cnaes_company_cnae"),
    )
    op.create_index("ix_company_cnaes_company_id", "company_cnaes", ["company_id"], unique=False)
    op.create_index("ix_company_cnaes_cnae", "company_cnaes", ["cnae"], unique=False)
    op.create_index("ix_company_cnaes_company_active", "company_cnaes", ["company_id", "active"], unique=False)
    op.create_index("ix_company_cnaes_cnae_active", "company_cnaes", ["cnae", "active"], unique=False)
    op.execute(
        """
        create unique index ux_company_cnaes_active_primary_per_company
        on company_cnaes (company_id)
        where active = true and is_primary = true
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists ux_company_cnaes_active_primary_per_company")
    op.drop_index("ix_company_cnaes_cnae_active", table_name="company_cnaes")
    op.drop_index("ix_company_cnaes_company_active", table_name="company_cnaes")
    op.drop_index("ix_company_cnaes_cnae", table_name="company_cnaes")
    op.drop_index("ix_company_cnaes_company_id", table_name="company_cnaes")
    op.drop_table("company_cnaes")
