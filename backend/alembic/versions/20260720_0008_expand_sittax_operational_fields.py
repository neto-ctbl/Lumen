from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260720_0008"
down_revision = "20260717_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sittax_fiscal_document_snapshots", sa.Column("issuer_name", sa.String(length=255), nullable=True))
    op.add_column("sittax_fiscal_document_snapshots", sa.Column("recipient_name", sa.String(length=255), nullable=True))
    op.add_column("sittax_fiscal_document_snapshots", sa.Column("issuer_document", sa.String(length=20), nullable=True))
    op.add_column("sittax_fiscal_document_snapshots", sa.Column("imported", sa.Boolean(), nullable=True))

    op.add_column("sittax_task_snapshots", sa.Column("company_name", sa.String(length=255), nullable=True))
    op.add_column("sittax_task_snapshots", sa.Column("status_code", sa.BigInteger(), nullable=True))
    op.add_column("sittax_task_snapshots", sa.Column("file_name", sa.String(length=255), nullable=True))
    op.add_column("sittax_task_snapshots", sa.Column("file_extension", sa.String(length=20), nullable=True))
    op.add_column("sittax_task_snapshots", sa.Column("file_extension_code", sa.BigInteger(), nullable=True))
    op.add_column("sittax_task_snapshots", sa.Column("processing_time_seconds", sa.Numeric(precision=14, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column("sittax_task_snapshots", "processing_time_seconds")
    op.drop_column("sittax_task_snapshots", "file_extension_code")
    op.drop_column("sittax_task_snapshots", "file_extension")
    op.drop_column("sittax_task_snapshots", "file_name")
    op.drop_column("sittax_task_snapshots", "status_code")
    op.drop_column("sittax_task_snapshots", "company_name")

    op.drop_column("sittax_fiscal_document_snapshots", "imported")
    op.drop_column("sittax_fiscal_document_snapshots", "issuer_document")
    op.drop_column("sittax_fiscal_document_snapshots", "recipient_name")
    op.drop_column("sittax_fiscal_document_snapshots", "issuer_name")
