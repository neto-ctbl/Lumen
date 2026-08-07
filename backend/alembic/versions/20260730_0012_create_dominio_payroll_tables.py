from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260730_0012"
down_revision = "20260724_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dominio_payroll_imports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("assessment_period_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("evidence_source", sa.String(length=50), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("selection_scope", sa.String(length=30), server_default="UNKNOWN", nullable=False),
        sa.Column("source_filter_name", sa.String(length=100), nullable=True),
        sa.Column("target_company_count", sa.Integer(), nullable=True),
        sa.Column("target_list_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("source_file_path", sa.String(length=500), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("physical_page_count", sa.Integer(), nullable=False),
        sa.Column("source_competences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assessment_competences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_companies", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_matched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_unmatched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_invalid_cnpj", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_missing_cnpj", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_ambiguous", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_warnings", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_errors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "file_sha256", name="uq_dominio_payroll_imports_org_sha256"),
    )
    op.create_index("ix_dominio_payroll_imports_file_sha256", "dominio_payroll_imports", ["file_sha256"], unique=False)
    op.create_index(op.f("ix_dominio_payroll_imports_assessment_period_id"), "dominio_payroll_imports", ["assessment_period_id"], unique=False)
    op.create_index("ix_dominio_payroll_imports_org_imported", "dominio_payroll_imports", ["organization_id", "imported_at"], unique=False)
    op.create_index("ix_dominio_payroll_imports_org_status", "dominio_payroll_imports", ["organization_id", "status"], unique=False)
    op.create_index(op.f("ix_dominio_payroll_imports_organization_id"), "dominio_payroll_imports", ["organization_id"], unique=False)

    op.create_table(
        "dominio_payroll_company_movements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("import_id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=True),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=True),
        sa.Column("source_company_key", sa.String(length=255), nullable=False),
        sa.Column("dominio_company_code", sa.String(length=50), nullable=False),
        sa.Column("company_cnpj", sa.String(length=18), nullable=True),
        sa.Column("source_company_name", sa.String(length=255), nullable=False),
        sa.Column("source_payroll_competence", sa.Date(), nullable=True),
        sa.Column("assessment_competence", sa.Date(), nullable=True),
        sa.Column("match_status", sa.String(length=30), nullable=False),
        sa.Column("parser_confidence", sa.String(length=30), nullable=False),
        sa.Column("calculation_type", sa.String(length=255), nullable=True),
        sa.Column("has_payroll", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_employee", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_pro_labore", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_autonomous", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_inss", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_fgts", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_termination", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_vacation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_leave", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("gross_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("discount_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("informative_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("net_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("source_page_start", sa.Integer(), nullable=True),
        sa.Column("source_page_end", sa.Integer(), nullable=True),
        sa.Column("source_page_count", sa.Integer(), nullable=False),
        sa.Column("source_page_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("declared_page_count", sa.Integer(), nullable=True),
        sa.Column("movement_hash", sa.String(length=64), nullable=False),
        sa.Column("rubrics_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["external_company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["import_id"], ["dominio_payroll_imports.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_id", "source_company_key", name="uq_dominio_payroll_movements_import_company_key"),
    )
    op.create_index(op.f("ix_dominio_payroll_company_movements_external_company_id"), "dominio_payroll_company_movements", ["external_company_id"], unique=False)
    op.create_index(op.f("ix_dominio_payroll_company_movements_fiscal_period_id"), "dominio_payroll_company_movements", ["fiscal_period_id"], unique=False)
    op.create_index(op.f("ix_dominio_payroll_company_movements_import_id"), "dominio_payroll_company_movements", ["import_id"], unique=False)
    op.create_index("ix_dominio_payroll_movements_movement_hash", "dominio_payroll_company_movements", ["movement_hash"], unique=False)
    op.create_index("ix_dominio_payroll_movements_org_match_status", "dominio_payroll_company_movements", ["organization_id", "match_status"], unique=False)
    op.create_index("ix_dominio_payroll_movements_org_period", "dominio_payroll_company_movements", ["organization_id", "fiscal_period_id"], unique=False)
    op.create_index(op.f("ix_dominio_payroll_company_movements_organization_id"), "dominio_payroll_company_movements", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dominio_payroll_company_movements_organization_id"), table_name="dominio_payroll_company_movements")
    op.drop_index("ix_dominio_payroll_movements_org_period", table_name="dominio_payroll_company_movements")
    op.drop_index("ix_dominio_payroll_movements_org_match_status", table_name="dominio_payroll_company_movements")
    op.drop_index("ix_dominio_payroll_movements_movement_hash", table_name="dominio_payroll_company_movements")
    op.drop_index(op.f("ix_dominio_payroll_company_movements_import_id"), table_name="dominio_payroll_company_movements")
    op.drop_index(op.f("ix_dominio_payroll_company_movements_fiscal_period_id"), table_name="dominio_payroll_company_movements")
    op.drop_index(op.f("ix_dominio_payroll_company_movements_external_company_id"), table_name="dominio_payroll_company_movements")
    op.drop_table("dominio_payroll_company_movements")

    op.drop_index(op.f("ix_dominio_payroll_imports_organization_id"), table_name="dominio_payroll_imports")
    op.drop_index("ix_dominio_payroll_imports_org_status", table_name="dominio_payroll_imports")
    op.drop_index("ix_dominio_payroll_imports_org_imported", table_name="dominio_payroll_imports")
    op.drop_index(op.f("ix_dominio_payroll_imports_assessment_period_id"), table_name="dominio_payroll_imports")
    op.drop_index("ix_dominio_payroll_imports_file_sha256", table_name="dominio_payroll_imports")
    op.drop_table("dominio_payroll_imports")
