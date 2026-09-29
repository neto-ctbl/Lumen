"""add Dominio company code to external companies

Revision ID: 20260925_0020
Revises: 20260911_0019
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0020"
down_revision = "20260911_0019"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_external_companies_org_dominio_company_code"


def upgrade() -> None:
    op.add_column(
        "external_companies",
        sa.Column("dominio_company_code", sa.String(length=50), nullable=True),
    )
    op.create_index(
        INDEX_NAME,
        "external_companies",
        ["organization_id", "dominio_company_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="external_companies")
    op.drop_column("external_companies", "dominio_company_code")
