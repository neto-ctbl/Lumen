from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260721_0009"
down_revision = "20260720_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "econet_cnae_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("cnae", sa.String(length=7), nullable=False),
        sa.Column("cnae_formatted", sa.String(length=10), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("econet_id_cnae", sa.String(length=100), nullable=False),
        sa.Column("activity_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("simples_status", sa.String(length=32), nullable=False),
        sa.Column("simples_allowed", sa.Boolean(), nullable=True),
        sa.Column("simples_annex_default", sa.String(length=20), nullable=True),
        sa.Column("simples_annex_conditional", sa.String(length=20), nullable=True),
        sa.Column("factor_r_applicable", sa.Boolean(), nullable=True),
        sa.Column("factor_r_threshold", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("mei_status", sa.String(length=32), nullable=False),
        sa.Column("mei_allowed", sa.Boolean(), nullable=True),
        sa.Column("mei_occupation", sa.String(length=255), nullable=True),
        sa.Column("presumed_profit_status", sa.String(length=32), nullable=False),
        sa.Column("presumed_profit_allowed", sa.Boolean(), nullable=True),
        sa.Column("presumed_profit_irpj_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("presumed_profit_csll_rate", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("actual_profit_status", sa.String(length=32), nullable=False),
        sa.Column("actual_profit_mandatory", sa.Boolean(), nullable=True),
        sa.Column("obligations_general", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("obligations_simples", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("obligations_simei", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unmapped_obligations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parse_status", sa.String(length=20), nullable=False),
        sa.Column("parser_version", sa.String(length=20), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(cnae) = 7 AND cnae ~ '^[0-9]+$'", name="ck_econet_cnae_cache_cnae_digits"),
        sa.CheckConstraint(
            "parse_status IN ('PARSED', 'PARTIAL', 'PARSE_ERROR')",
            name="ck_econet_cnae_cache_parse_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cnae", name="uq_econet_cnae_cache_cnae"),
    )
    op.create_index("ix_econet_cnae_cache_econet_id_cnae", "econet_cnae_cache", ["econet_id_cnae"], unique=False)
    op.create_index("ix_econet_cnae_cache_expires_at", "econet_cnae_cache", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_econet_cnae_cache_expires_at", table_name="econet_cnae_cache")
    op.drop_index("ix_econet_cnae_cache_econet_id_cnae", table_name="econet_cnae_cache")
    op.drop_table("econet_cnae_cache")
