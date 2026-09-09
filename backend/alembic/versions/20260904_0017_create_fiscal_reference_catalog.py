"""create fiscal reference catalog

Revision ID: 20260904_0017
Revises: 20260902_0016
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260904_0017"
down_revision = "20260902_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fiscal_reference_datasets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("source_title", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=100), nullable=True),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rows_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "source_kind",
            "file_sha256",
            "parser_version",
            name="uq_fiscal_reference_datasets_kind_sha256_parser",
        ),
    )
    op.create_index("ix_fiscal_reference_datasets_source_kind", "fiscal_reference_datasets", ["source_kind"])
    op.create_index("ux_fiscal_reference_datasets_one_active_kind", "fiscal_reference_datasets", ["source_kind"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_table(
        "fiscal_reference_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.BigInteger(), sa.ForeignKey("fiscal_reference_datasets.id"), nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("source_sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        *[sa.Column(name, typ, nullable=True) for name, typ in [
            ("cnae", sa.String(20)), ("cnae_formatted", sa.String(20)), ("cnae_description", sa.Text()),
            ("lc116_item", sa.String(20)), ("lc116_item_formatted", sa.String(20)), ("lc116_description", sa.Text()),
            ("iss_rate", sa.Numeric(12, 6)), ("allows_tax_outside", sa.Boolean()), ("lc116_inciso", sa.String(255)),
            ("trib_nac_code", sa.String(50)), ("trib_nac_description", sa.Text()), ("nbs", sa.String(50)),
            ("nbs_formatted", sa.String(50)), ("nbs_description", sa.Text()), ("class_trib_code", sa.String(50)),
            ("class_trib_description", sa.Text()), ("cst_code", sa.String(50)), ("cst_description", sa.Text()),
            ("indop_code", sa.String(50)), ("indop_description", sa.Text()), ("onerous", sa.Boolean()),
            ("foreign_acquisition", sa.Boolean()), ("ibs_incidence_location", sa.Text()),
        ]],
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("dataset_id", "source_sheet", "source_row_number", "source_kind", name="uq_fiscal_reference_entries_physical_row"),
    )
    for name, column in [("ix_fiscal_reference_entries_dataset_id", "dataset_id"), ("ix_fiscal_reference_entries_source_kind", "source_kind"), ("ix_fiscal_reference_entries_cnae", "cnae"), ("ix_fiscal_reference_entries_lc116_item", "lc116_item"), ("ix_fiscal_reference_entries_nbs", "nbs"), ("ix_fiscal_reference_entries_trib_nac_code", "trib_nac_code"), ("ix_fiscal_reference_entries_class_trib_code", "class_trib_code"), ("ix_fiscal_reference_entries_cst_code", "cst_code"), ("ix_fiscal_reference_entries_indop_code", "indop_code")]:
        op.create_index(name, "fiscal_reference_entries", [column])


def downgrade() -> None:
    for name in ["ix_fiscal_reference_entries_indop_code", "ix_fiscal_reference_entries_cst_code", "ix_fiscal_reference_entries_class_trib_code", "ix_fiscal_reference_entries_trib_nac_code", "ix_fiscal_reference_entries_nbs", "ix_fiscal_reference_entries_lc116_item", "ix_fiscal_reference_entries_cnae", "ix_fiscal_reference_entries_source_kind", "ix_fiscal_reference_entries_dataset_id"]:
        op.drop_index(name, table_name="fiscal_reference_entries")
    op.drop_table("fiscal_reference_entries")
    op.drop_index("ux_fiscal_reference_datasets_one_active_kind", table_name="fiscal_reference_datasets")
    op.drop_index("ix_fiscal_reference_datasets_source_kind", table_name="fiscal_reference_datasets")
    op.drop_table("fiscal_reference_datasets")
