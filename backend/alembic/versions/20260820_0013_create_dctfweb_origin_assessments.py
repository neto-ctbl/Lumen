from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260820_0013"
down_revision = "20260730_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dctfweb_origin_assessments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("external_company_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_period_id", sa.BigInteger(), nullable=False),
        sa.Column("assessment_competence", sa.Date(), nullable=False),
        sa.Column("source_payroll_competence", sa.Date(), nullable=True),
        sa.Column("dp_coverage_status", sa.String(length=30), nullable=False),
        sa.Column("dp_signal_present", sa.Boolean(), nullable=False),
        sa.Column("reinf_signal_present", sa.Boolean(), nullable=False),
        sa.Column("mit_signal_present", sa.Boolean(), nullable=False),
        sa.Column("fiscal_signal_present", sa.Boolean(), nullable=False),
        sa.Column("dctfweb_observed", sa.Boolean(), nullable=False),
        sa.Column("expected_origin", sa.String(length=30), nullable=False),
        sa.Column("expected_responsible_department", sa.String(length=30), nullable=True),
        sa.Column("classification_confidence", sa.String(length=20), nullable=False),
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
            "organization_id",
            "external_company_id",
            "fiscal_period_id",
            name="uq_dctfweb_origin_assessments_org_company_period",
        ),
    )
    op.create_index(
        "ix_dctfweb_origin_assessments_org_period",
        "dctfweb_origin_assessments",
        ["organization_id", "fiscal_period_id"],
        unique=False,
    )
    op.create_index(
        "ix_dctfweb_origin_assessments_org_company",
        "dctfweb_origin_assessments",
        ["organization_id", "external_company_id"],
        unique=False,
    )
    op.create_index(
        "ix_dctfweb_origin_assessments_origin",
        "dctfweb_origin_assessments",
        ["expected_origin"],
        unique=False,
    )
    op.create_index(
        "ix_dctfweb_origin_assessments_department",
        "dctfweb_origin_assessments",
        ["expected_responsible_department"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dctfweb_origin_assessments_organization_id"),
        "dctfweb_origin_assessments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dctfweb_origin_assessments_external_company_id"),
        "dctfweb_origin_assessments",
        ["external_company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dctfweb_origin_assessments_fiscal_period_id"),
        "dctfweb_origin_assessments",
        ["fiscal_period_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dctfweb_origin_assessments_fiscal_period_id"), table_name="dctfweb_origin_assessments")
    op.drop_index(op.f("ix_dctfweb_origin_assessments_external_company_id"), table_name="dctfweb_origin_assessments")
    op.drop_index(op.f("ix_dctfweb_origin_assessments_organization_id"), table_name="dctfweb_origin_assessments")
    op.drop_index("ix_dctfweb_origin_assessments_department", table_name="dctfweb_origin_assessments")
    op.drop_index("ix_dctfweb_origin_assessments_origin", table_name="dctfweb_origin_assessments")
    op.drop_index("ix_dctfweb_origin_assessments_org_company", table_name="dctfweb_origin_assessments")
    op.drop_index("ix_dctfweb_origin_assessments_org_period", table_name="dctfweb_origin_assessments")
    op.drop_table("dctfweb_origin_assessments")
