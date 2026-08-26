from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260824_0014"
down_revision = "20260820_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factor_r_assessments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=False),
        sa.Column("applicability_status", sa.String(length=30), nullable=False),
        sa.Column("calculation_status", sa.String(length=40), nullable=False),
        sa.Column("payroll_window_start", sa.Date(), nullable=False),
        sa.Column("payroll_window_end", sa.Date(), nullable=False),
        sa.Column("payroll_months_expected", sa.Integer(), nullable=False),
        sa.Column("payroll_months_covered", sa.Integer(), nullable=False),
        sa.Column("payroll_months_with_movement", sa.Integer(), nullable=False),
        sa.Column("payroll_months_confirmed_zero", sa.Integer(), nullable=False),
        sa.Column("payroll_months_missing", sa.Integer(), nullable=False),
        sa.Column("fs12_dominio_estimate", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("fs12_confidence", sa.String(length=20), nullable=False),
        sa.Column("fs12_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rbt12_value", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("rbt12_source", sa.String(length=30), nullable=True),
        sa.Column("rbt12_confidence", sa.String(length=20), nullable=False),
        sa.Column("factor_r_estimated_dominio", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("estimated_threshold_side", sa.String(length=30), nullable=True),
        sa.Column("estimated_annex", sa.String(length=10), nullable=True),
        sa.Column("factor_r_sittax_observed", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("sittax_observed_annexes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("factor_r_delta", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=30), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["external_company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["fiscal_period_id"], ["fiscal_periods.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "external_company_id", "fiscal_period_id", name="uq_factor_r_assessments_org_company_period"
        ),
    )
    for name, columns in (
        ("ix_factor_r_assessments_org_period", ["organization_id", "fiscal_period_id"]),
        ("ix_factor_r_assessments_org_company", ["organization_id", "external_company_id"]),
        ("ix_factor_r_assessments_applicability", ["applicability_status"]),
        ("ix_factor_r_assessments_reconciliation", ["reconciliation_status"]),
        (op.f("ix_factor_r_assessments_organization_id"), ["organization_id"]),
        (op.f("ix_factor_r_assessments_external_company_id"), ["external_company_id"]),
        (op.f("ix_factor_r_assessments_fiscal_period_id"), ["fiscal_period_id"]),
    ):
        op.create_index(name, "factor_r_assessments", columns, unique=False)


def downgrade() -> None:
    for name in (
        op.f("ix_factor_r_assessments_fiscal_period_id"),
        op.f("ix_factor_r_assessments_external_company_id"),
        op.f("ix_factor_r_assessments_organization_id"),
        "ix_factor_r_assessments_reconciliation",
        "ix_factor_r_assessments_applicability",
        "ix_factor_r_assessments_org_company",
        "ix_factor_r_assessments_org_period",
    ):
        op.drop_index(name, table_name="factor_r_assessments")
    op.drop_table("factor_r_assessments")
