from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260716_0006"
down_revision = "20260716_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sittax_apuracao_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_company_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=True),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_apuracao_id", sa.String(length=100), nullable=False),
        sa.Column("company_cnpj", sa.String(length=14), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("period_reference", sa.String(length=7), nullable=False),
        sa.Column("is_transmitted", sa.Boolean(), nullable=True),
        sa.Column("transmission_in_progress", sa.Boolean(), nullable=True),
        sa.Column("transmission_type", sa.String(length=100), nullable=True),
        sa.Column("transmitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("net_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("product_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("service_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("return_revenue", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("rbt12", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("rba", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("das_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("das_xml_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("factor_r_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("company_has_payroll", sa.Boolean(), nullable=True),
        sa.Column("taxes_icms", sa.Boolean(), nullable=True),
        sa.Column("taxes_iss", sa.Boolean(), nullable=True),
        sa.Column("taxes_ipi", sa.Boolean(), nullable=True),
        sa.Column("taxes_pis_cofins", sa.Boolean(), nullable=True),
        sa.Column("companies_apuracao", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("annexes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cfops", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("activities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payrolls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("alerts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["external_company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sittax_company_snapshot_id"], ["sittax_company_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "fiscal_period_id",
            name="uq_sittax_apuracao_snapshots_org_company_period",
        ),
    )
    op.create_index(
        "ix_sittax_apuracao_snapshots_org_period",
        "sittax_apuracao_snapshots",
        ["organization_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(
        "ix_sittax_apuracao_snapshots_org_external_period",
        "sittax_apuracao_snapshots",
        ["organization_id", "external_company_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_apuracao_snapshots_external_company_id"),
        "sittax_apuracao_snapshots",
        ["external_company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_apuracao_snapshots_fiscal_period_id"),
        "sittax_apuracao_snapshots",
        ["fiscal_period_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_apuracao_snapshots_organization_id"),
        "sittax_apuracao_snapshots",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sittax_apuracao_snapshots_sittax_company_snapshot_id"),
        "sittax_apuracao_snapshots",
        ["sittax_company_snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sittax_apuracao_snapshots_sittax_company_snapshot_id"),
        table_name="sittax_apuracao_snapshots",
    )
    op.drop_index(op.f("ix_sittax_apuracao_snapshots_organization_id"), table_name="sittax_apuracao_snapshots")
    op.drop_index(op.f("ix_sittax_apuracao_snapshots_fiscal_period_id"), table_name="sittax_apuracao_snapshots")
    op.drop_index(op.f("ix_sittax_apuracao_snapshots_external_company_id"), table_name="sittax_apuracao_snapshots")
    op.drop_index("ix_sittax_apuracao_snapshots_org_external_period", table_name="sittax_apuracao_snapshots")
    op.drop_index("ix_sittax_apuracao_snapshots_org_period", table_name="sittax_apuracao_snapshots")
    op.drop_table("sittax_apuracao_snapshots")
