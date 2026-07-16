from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260716_0005"
down_revision = "20260714_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sittax_company_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("sittax_company_id", sa.String(length=100), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("state_registration", sa.String(length=50), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("homologated", sa.Boolean(), nullable=True),
        sa.Column("cash_regime", sa.Boolean(), nullable=True),
        sa.Column("match_status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "sittax_company_id", name="uq_sittax_company_snapshots_org_company"),
    )
    op.create_index(
        "ix_sittax_company_snapshots_org_cnpj",
        "sittax_company_snapshots",
        ["organization_id", "cnpj"],
        unique=False,
    )
    op.create_index(
        "ix_sittax_company_snapshots_org_company",
        "sittax_company_snapshots",
        ["organization_id", "company_id"],
        unique=False,
    )
    op.create_index(
        "ix_sittax_company_snapshots_org_match",
        "sittax_company_snapshots",
        ["organization_id", "match_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_company_snapshots_company_id"),
        "sittax_company_snapshots",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_company_snapshots_organization_id"),
        "sittax_company_snapshots",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sittax_company_snapshots_organization_id"), table_name="sittax_company_snapshots")
    op.drop_index(op.f("ix_sittax_company_snapshots_company_id"), table_name="sittax_company_snapshots")
    op.drop_index("ix_sittax_company_snapshots_org_match", table_name="sittax_company_snapshots")
    op.drop_index("ix_sittax_company_snapshots_org_company", table_name="sittax_company_snapshots")
    op.drop_index("ix_sittax_company_snapshots_org_cnpj", table_name="sittax_company_snapshots")
    op.drop_table("sittax_company_snapshots")
