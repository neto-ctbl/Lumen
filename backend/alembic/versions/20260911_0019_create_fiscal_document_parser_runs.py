"""create fiscal document parser runs

Revision ID: 20260911_0019
Revises: 20260911_0018
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260911_0019"
down_revision = "20260911_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fiscal_document_parser_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("document_family", sa.String(length=100), nullable=False),
        sa.Column("extraction_status", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "structured_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "extraction_status IN ('MATCHED', 'UNSUPPORTED', 'INCONCLUSIVE', 'INVALID', 'ERROR')",
            name="ck_fiscal_doc_parser_runs_extraction_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_fiscal_doc_parser_runs_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["fiscal_evidence_id"],
            ["fiscal_evidences.id"],
            name="fk_fiscal_doc_parser_runs_evidence_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_fiscal_doc_parser_runs_organization_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "fiscal_evidence_id",
            "parser_name",
            "parser_version",
            name="uq_fiscal_doc_parser_runs_org_evidence_parser_version",
        ),
    )
    op.create_index(
        "ix_fiscal_doc_parser_runs_org_evidence",
        "fiscal_document_parser_runs",
        ["organization_id", "fiscal_evidence_id"],
        unique=False,
    )
    op.create_index(
        "ix_fiscal_doc_parser_runs_org_status",
        "fiscal_document_parser_runs",
        ["organization_id", "extraction_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fiscal_doc_parser_runs_org_status", table_name="fiscal_document_parser_runs")
    op.drop_index("ix_fiscal_doc_parser_runs_org_evidence", table_name="fiscal_document_parser_runs")
    op.drop_table("fiscal_document_parser_runs")
