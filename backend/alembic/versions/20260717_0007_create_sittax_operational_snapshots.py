from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260717_0007"
down_revision = "20260716_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sittax_difal_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_company_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_apuracao_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=True),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=False),
        sa.Column("company_cnpj", sa.String(length=14), nullable=False),
        sa.Column("period_reference", sa.String(length=7), nullable=False),
        sa.Column("has_guide", sa.Boolean(), nullable=True),
        sa.Column("dare_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("resale_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("use_consumption_fixed_asset_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("closing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transmission_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_purchases", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("notes_without_type_or_reference", sa.Boolean(), nullable=True),
        sa.Column("inconsistencies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["external_company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sittax_apuracao_snapshot_id"], ["sittax_apuracao_snapshots.id"]),
        sa.ForeignKeyConstraint(["sittax_company_snapshot_id"], ["sittax_company_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "fiscal_period_id",
            name="uq_sittax_difal_snapshots_org_company_period",
        ),
    )
    op.create_index("ix_sittax_difal_snapshots_org_period", "sittax_difal_snapshots", ["organization_id", "fiscal_period_id"], unique=False)
    op.create_index(
        "ix_sittax_difal_snapshots_org_external_period",
        "sittax_difal_snapshots",
        ["organization_id", "external_company_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(op.f("ix_sittax_difal_snapshots_organization_id"), "sittax_difal_snapshots", ["organization_id"], unique=False)
    op.create_index(op.f("ix_sittax_difal_snapshots_sittax_company_snapshot_id"), "sittax_difal_snapshots", ["sittax_company_snapshot_id"], unique=False)
    op.create_index(op.f("ix_sittax_difal_snapshots_sittax_apuracao_snapshot_id"), "sittax_difal_snapshots", ["sittax_apuracao_snapshot_id"], unique=False)
    op.create_index(op.f("ix_sittax_difal_snapshots_external_company_id"), "sittax_difal_snapshots", ["external_company_id"], unique=False)
    op.create_index(op.f("ix_sittax_difal_snapshots_fiscal_period_id"), "sittax_difal_snapshots", ["fiscal_period_id"], unique=False)

    op.create_table(
        "sittax_fiscal_document_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_company_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("sittax_apuracao_snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=True),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=False),
        sa.Column("source_document_key", sa.String(length=255), nullable=False),
        sa.Column("sittax_document_id", sa.String(length=100), nullable=True),
        sa.Column("document_direction", sa.String(length=20), nullable=False),
        sa.Column("access_key", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=20), nullable=True),
        sa.Column("document_number", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_reference", sa.String(length=7), nullable=False),
        sa.Column("issuer_state", sa.String(length=2), nullable=True),
        sa.Column("recipient_state", sa.String(length=2), nullable=True),
        sa.Column("cfops", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("import_source", sa.String(length=100), nullable=True),
        sa.Column("has_xml", sa.Boolean(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["external_company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["sittax_apuracao_snapshot_id"], ["sittax_apuracao_snapshots.id"]),
        sa.ForeignKeyConstraint(["sittax_company_snapshot_id"], ["sittax_company_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "document_direction",
            "source_document_key",
            name="uq_sittax_fdoc_snapshots_org_company_dir_source",
        ),
    )
    op.create_index("ix_sittax_fiscal_document_snapshots_org_period", "sittax_fiscal_document_snapshots", ["organization_id", "fiscal_period_id"], unique=False)
    op.create_index(
        "ix_sittax_fiscal_document_snapshots_org_external_period",
        "sittax_fiscal_document_snapshots",
        ["organization_id", "external_company_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(op.f("ix_sittax_fiscal_document_snapshots_organization_id"), "sittax_fiscal_document_snapshots", ["organization_id"], unique=False)
    op.create_index(op.f("ix_sittax_fiscal_document_snapshots_sittax_company_snapshot_id"), "sittax_fiscal_document_snapshots", ["sittax_company_snapshot_id"], unique=False)
    op.create_index(op.f("ix_sittax_fiscal_document_snapshots_sittax_apuracao_snapshot_id"), "sittax_fiscal_document_snapshots", ["sittax_apuracao_snapshot_id"], unique=False)
    op.create_index(op.f("ix_sittax_fiscal_document_snapshots_external_company_id"), "sittax_fiscal_document_snapshots", ["external_company_id"], unique=False)
    op.create_index(op.f("ix_sittax_fiscal_document_snapshots_fiscal_period_id"), "sittax_fiscal_document_snapshots", ["fiscal_period_id"], unique=False)

    op.create_table(
        "sittax_task_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("source_task_key", sa.String(length=255), nullable=False),
        sa.Column("sittax_task_id", sa.String(length=100), nullable=True),
        sa.Column("sittax_company_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("external_company_id", sa.BigInteger(), nullable=True),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=True),
        sa.Column("task_type", sa.String(length=100), nullable=True),
        sa.Column("task_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("company_cnpj", sa.String(length=14), nullable=True),
        sa.Column("period_reference", sa.String(length=7), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_user_id", sa.String(length=100), nullable=True),
        sa.Column("source_user_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("has_file", sa.Boolean(), nullable=True),
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
        sa.UniqueConstraint("organization_id", "source_task_key", name="uq_sittax_task_snapshots_org_source_key"),
    )
    op.create_index("ix_sittax_task_snapshots_org_period", "sittax_task_snapshots", ["organization_id", "fiscal_period_id"], unique=False)
    op.create_index(
        "ix_sittax_task_snapshots_org_external_period",
        "sittax_task_snapshots",
        ["organization_id", "external_company_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(op.f("ix_sittax_task_snapshots_organization_id"), "sittax_task_snapshots", ["organization_id"], unique=False)
    op.create_index(op.f("ix_sittax_task_snapshots_sittax_company_snapshot_id"), "sittax_task_snapshots", ["sittax_company_snapshot_id"], unique=False)
    op.create_index(op.f("ix_sittax_task_snapshots_external_company_id"), "sittax_task_snapshots", ["external_company_id"], unique=False)
    op.create_index(op.f("ix_sittax_task_snapshots_fiscal_period_id"), "sittax_task_snapshots", ["fiscal_period_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sittax_task_snapshots_fiscal_period_id"), table_name="sittax_task_snapshots")
    op.drop_index(op.f("ix_sittax_task_snapshots_external_company_id"), table_name="sittax_task_snapshots")
    op.drop_index(op.f("ix_sittax_task_snapshots_sittax_company_snapshot_id"), table_name="sittax_task_snapshots")
    op.drop_index(op.f("ix_sittax_task_snapshots_organization_id"), table_name="sittax_task_snapshots")
    op.drop_index("ix_sittax_task_snapshots_org_external_period", table_name="sittax_task_snapshots")
    op.drop_index("ix_sittax_task_snapshots_org_period", table_name="sittax_task_snapshots")
    op.drop_table("sittax_task_snapshots")

    op.drop_index(op.f("ix_sittax_fiscal_document_snapshots_fiscal_period_id"), table_name="sittax_fiscal_document_snapshots")
    op.drop_index(op.f("ix_sittax_fiscal_document_snapshots_external_company_id"), table_name="sittax_fiscal_document_snapshots")
    op.drop_index(op.f("ix_sittax_fiscal_document_snapshots_sittax_apuracao_snapshot_id"), table_name="sittax_fiscal_document_snapshots")
    op.drop_index(op.f("ix_sittax_fiscal_document_snapshots_sittax_company_snapshot_id"), table_name="sittax_fiscal_document_snapshots")
    op.drop_index(op.f("ix_sittax_fiscal_document_snapshots_organization_id"), table_name="sittax_fiscal_document_snapshots")
    op.drop_index("ix_sittax_fiscal_document_snapshots_org_external_period", table_name="sittax_fiscal_document_snapshots")
    op.drop_index("ix_sittax_fiscal_document_snapshots_org_period", table_name="sittax_fiscal_document_snapshots")
    op.drop_table("sittax_fiscal_document_snapshots")

    op.drop_index(op.f("ix_sittax_difal_snapshots_fiscal_period_id"), table_name="sittax_difal_snapshots")
    op.drop_index(op.f("ix_sittax_difal_snapshots_external_company_id"), table_name="sittax_difal_snapshots")
    op.drop_index(op.f("ix_sittax_difal_snapshots_sittax_apuracao_snapshot_id"), table_name="sittax_difal_snapshots")
    op.drop_index(op.f("ix_sittax_difal_snapshots_sittax_company_snapshot_id"), table_name="sittax_difal_snapshots")
    op.drop_index(op.f("ix_sittax_difal_snapshots_organization_id"), table_name="sittax_difal_snapshots")
    op.drop_index("ix_sittax_difal_snapshots_org_external_period", table_name="sittax_difal_snapshots")
    op.drop_index("ix_sittax_difal_snapshots_org_period", table_name="sittax_difal_snapshots")
    op.drop_table("sittax_difal_snapshots")
