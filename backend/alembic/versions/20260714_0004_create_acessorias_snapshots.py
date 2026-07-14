from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260714_0004"
down_revision = "20260706_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acessorias_company_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("external_company_id", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=18), nullable=False),
        sa.Column("razao_social", sa.String(length=255), nullable=False),
        sa.Column("nome_fantasia", sa.String(length=255), nullable=True),
        sa.Column("external_status", sa.String(length=100), nullable=True),
        sa.Column("regime_raw", sa.String(length=255), nullable=True),
        sa.Column("regime_code", sa.Integer(), nullable=True),
        sa.Column("regime_canonical", sa.String(length=100), nullable=True),
        sa.Column("regime_mapping_status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "external_company_id", name="uq_acessorias_company_snapshots_org_external"),
    )
    op.create_index(
        "ix_acessorias_company_snapshots_org_identifier",
        "acessorias_company_snapshots",
        ["organization_id", "identifier"],
        unique=False,
    )
    op.create_index(
        "ix_acessorias_company_snapshots_org_company",
        "acessorias_company_snapshots",
        ["organization_id", "company_id"],
        unique=False,
    )
    op.create_index(
        "ix_acessorias_company_snapshots_org_regime",
        "acessorias_company_snapshots",
        ["organization_id", "regime_canonical"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_company_snapshots_company_id"),
        "acessorias_company_snapshots",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_company_snapshots_organization_id"),
        "acessorias_company_snapshots",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "acessorias_delivery_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("period_id", sa.BigInteger(), nullable=True),
        sa.Column("company_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("external_company_id", sa.String(length=100), nullable=False),
        sa.Column("identifier", sa.String(length=18), nullable=False),
        sa.Column("external_delivery_id", sa.String(length=100), nullable=False),
        sa.Column("external_item_id", sa.String(length=100), nullable=True),
        sa.Column("external_type", sa.String(length=10), nullable=True),
        sa.Column("obligation_name", sa.String(length=255), nullable=False),
        sa.Column("obligation_id", sa.Integer(), nullable=True),
        sa.Column("obligation_mapping_status", sa.String(length=20), nullable=False),
        sa.Column("external_status", sa.String(length=100), nullable=True),
        sa.Column("normalized_status", sa.String(length=50), nullable=False),
        sa.Column("competencia_raw", sa.String(length=50), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("delay_date", sa.Date(), nullable=True),
        sa.Column("delivered_date", sa.Date(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("guide_read_status", sa.String(length=20), nullable=True),
        sa.Column("has_penalty", sa.Boolean(), nullable=True),
        sa.Column("department_external_id", sa.String(length=100), nullable=True),
        sa.Column("department_name", sa.String(length=255), nullable=True),
        sa.Column("responsible_deadline_id", sa.String(length=100), nullable=True),
        sa.Column("responsible_deadline_name", sa.String(length=255), nullable=True),
        sa.Column("responsible_delivery_id", sa.String(length=100), nullable=True),
        sa.Column("responsible_delivery_name", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["company_snapshot_id"], ["acessorias_company_snapshots.id"]),
        sa.ForeignKeyConstraint(["obligation_id"], ["fiscal_obligations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["fiscal_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "external_company_id",
            "external_delivery_id",
            name="uq_acessorias_delivery_snapshots_org_company_delivery",
        ),
    )
    op.create_index(
        "ix_acessorias_delivery_snapshots_org_company",
        "acessorias_delivery_snapshots",
        ["organization_id", "company_id"],
        unique=False,
    )
    op.create_index(
        "ix_acessorias_delivery_snapshots_org_period",
        "acessorias_delivery_snapshots",
        ["organization_id", "period_id"],
        unique=False,
    )
    op.create_index(
        "ix_acessorias_delivery_snapshots_org_mapping",
        "acessorias_delivery_snapshots",
        ["organization_id", "obligation_mapping_status"],
        unique=False,
    )
    op.create_index(
        "ix_acessorias_delivery_snapshots_org_changed",
        "acessorias_delivery_snapshots",
        ["organization_id", "external_last_changed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_delivery_snapshots_company_id"),
        "acessorias_delivery_snapshots",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_delivery_snapshots_company_snapshot_id"),
        "acessorias_delivery_snapshots",
        ["company_snapshot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_delivery_snapshots_obligation_id"),
        "acessorias_delivery_snapshots",
        ["obligation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_delivery_snapshots_organization_id"),
        "acessorias_delivery_snapshots",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_acessorias_delivery_snapshots_period_id"),
        "acessorias_delivery_snapshots",
        ["period_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_acessorias_delivery_snapshots_period_id"), table_name="acessorias_delivery_snapshots")
    op.drop_index(op.f("ix_acessorias_delivery_snapshots_organization_id"), table_name="acessorias_delivery_snapshots")
    op.drop_index(op.f("ix_acessorias_delivery_snapshots_obligation_id"), table_name="acessorias_delivery_snapshots")
    op.drop_index(op.f("ix_acessorias_delivery_snapshots_company_snapshot_id"), table_name="acessorias_delivery_snapshots")
    op.drop_index(op.f("ix_acessorias_delivery_snapshots_company_id"), table_name="acessorias_delivery_snapshots")
    op.drop_index("ix_acessorias_delivery_snapshots_org_changed", table_name="acessorias_delivery_snapshots")
    op.drop_index("ix_acessorias_delivery_snapshots_org_mapping", table_name="acessorias_delivery_snapshots")
    op.drop_index("ix_acessorias_delivery_snapshots_org_period", table_name="acessorias_delivery_snapshots")
    op.drop_index("ix_acessorias_delivery_snapshots_org_company", table_name="acessorias_delivery_snapshots")
    op.drop_table("acessorias_delivery_snapshots")

    op.drop_index(op.f("ix_acessorias_company_snapshots_organization_id"), table_name="acessorias_company_snapshots")
    op.drop_index(op.f("ix_acessorias_company_snapshots_company_id"), table_name="acessorias_company_snapshots")
    op.drop_index("ix_acessorias_company_snapshots_org_regime", table_name="acessorias_company_snapshots")
    op.drop_index("ix_acessorias_company_snapshots_org_company", table_name="acessorias_company_snapshots")
    op.drop_index("ix_acessorias_company_snapshots_org_identifier", table_name="acessorias_company_snapshots")
    op.drop_table("acessorias_company_snapshots")
