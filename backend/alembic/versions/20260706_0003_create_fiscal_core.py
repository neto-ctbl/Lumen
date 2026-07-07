from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260706_0003"
down_revision = "20260706_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_companies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("econtrole_company_id", sa.String(length=100), nullable=True),
        sa.Column("econtrole_profile_id", sa.String(length=100), nullable=True),
        sa.Column("cnpj", sa.String(length=18), nullable=False),
        sa.Column("razao_social", sa.String(length=255), nullable=False),
        sa.Column("nome_fantasia", sa.String(length=255), nullable=True),
        sa.Column("apelido_pasta", sa.String(length=255), nullable=True),
        sa.Column("situacao", sa.String(length=100), nullable=True),
        sa.Column("inscricao_estadual", sa.String(length=50), nullable=True),
        sa.Column("inscricao_municipal", sa.String(length=50), nullable=True),
        sa.Column("municipio", sa.String(length=120), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("cnae_principal", sa.String(length=20), nullable=True),
        sa.Column("cnaes_secundarios", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at_econtrole", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at_econtrole", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sync_status", sa.String(length=50), nullable=True),
        sa.Column("raw_econtrole", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "cnpj", name="uq_external_companies_org_cnpj"),
    )
    op.create_index("ix_external_companies_org_active", "external_companies", ["organization_id", "active"], unique=False)
    op.create_index(op.f("ix_external_companies_organization_id"), "external_companies", ["organization_id"], unique=False)

    op.create_table(
        "company_activity_types",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("activity_type", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "activity_type", "source", name="uq_company_activity_types_company_type_source"),
    )
    op.create_index(op.f("ix_company_activity_types_company_id"), "company_activity_types", ["company_id"], unique=False)

    op.create_table(
        "fiscal_periods",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("month >= 1 AND month <= 12", name="ck_fiscal_periods_month"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "competencia", name="uq_fiscal_periods_org_competencia"),
    )
    op.create_index(op.f("ix_fiscal_periods_organization_id"), "fiscal_periods", ["organization_id"], unique=False)

    op.create_table(
        "fiscal_obligations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("department_default", sa.String(length=30), nullable=False),
        sa.Column(
            "source_priority",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_fiscal_obligations_code"), "fiscal_obligations", ["code"], unique=True)

    op.create_table(
        "fiscal_obligation_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=True),
        sa.Column("obligation_id", sa.Integer(), nullable=False),
        sa.Column("regime", sa.String(length=100), nullable=True),
        sa.Column("activity_type", sa.String(length=80), nullable=True),
        sa.Column("rule_type", sa.String(length=100), nullable=False),
        sa.Column("condition_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["obligation_id"], ["fiscal_obligations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fiscal_obligation_rules_obligation_id"), "fiscal_obligation_rules", ["obligation_id"], unique=False)
    op.create_index(op.f("ix_fiscal_obligation_rules_organization_id"), "fiscal_obligation_rules", ["organization_id"], unique=False)

    op.create_table(
        "integration_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="INACTIVE", nullable=False),
        sa.Column("credentials_ref", sa.String(length=255), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_health_status", sa.String(length=50), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_accounts_organization_id"), "integration_accounts", ["organization_id"], unique=False)

    op.create_table(
        "fiscal_evidences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("period_id", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("detected_tax", sa.String(length=100), nullable=True),
        sa.Column("detected_obligation", sa.String(length=100), nullable=True),
        sa.Column("cnpj_detected", sa.String(length=18), nullable=True),
        sa.Column("ie_detected", sa.String(length=50), nullable=True),
        sa.Column("razao_social_detected", sa.String(length=255), nullable=True),
        sa.Column("competencia_detected", sa.String(length=7), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("amount_principal", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("amount_multa", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("amount_juros", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("document_number", sa.String(length=100), nullable=True),
        sa.Column("receipt_number", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=255), nullable=True),
        sa.Column("installment_protocol", sa.String(length=100), nullable=True),
        sa.Column("installment_current", sa.Integer(), nullable=True),
        sa.Column("installment_total", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="PENDENTE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["fiscal_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_evidences_file_hash", "fiscal_evidences", ["file_hash"], unique=False)
    op.create_index(op.f("ix_fiscal_evidences_company_id"), "fiscal_evidences", ["company_id"], unique=False)
    op.create_index(op.f("ix_fiscal_evidences_organization_id"), "fiscal_evidences", ["organization_id"], unique=False)
    op.create_index("ix_fiscal_evidences_org_period", "fiscal_evidences", ["organization_id", "period_id"], unique=False)
    op.create_index(op.f("ix_fiscal_evidences_period_id"), "fiscal_evidences", ["period_id"], unique=False)

    op.create_table(
        "fiscal_obligation_statuses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("period_id", sa.BigInteger(), nullable=False),
        sa.Column("obligation_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("responsible_department", sa.String(length=30), nullable=False),
        sa.Column("origin_reason", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("main_evidence_id", sa.BigInteger(), nullable=True),
        sa.Column("last_source", sa.String(length=50), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["main_evidence_id"], ["fiscal_evidences.id"]),
        sa.ForeignKeyConstraint(["obligation_id"], ["fiscal_obligations.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["fiscal_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "period_id", "obligation_id", name="uq_fiscal_status_company_period_obligation"),
    )
    op.create_index(op.f("ix_fiscal_obligation_statuses_company_id"), "fiscal_obligation_statuses", ["company_id"], unique=False)
    op.create_index(op.f("ix_fiscal_obligation_statuses_obligation_id"), "fiscal_obligation_statuses", ["obligation_id"], unique=False)
    op.create_index(op.f("ix_fiscal_obligation_statuses_organization_id"), "fiscal_obligation_statuses", ["organization_id"], unique=False)
    op.create_index("ix_fiscal_status_org_period_status", "fiscal_obligation_statuses", ["organization_id", "period_id", "status"], unique=False)
    op.create_index(op.f("ix_fiscal_obligation_statuses_period_id"), "fiscal_obligation_statuses", ["period_id"], unique=False)

    op.create_table(
        "fiscal_alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("period_id", sa.BigInteger(), nullable=True),
        sa.Column("obligation_status_id", sa.BigInteger(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("department", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("rule_key", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["obligation_status_id"], ["fiscal_obligation_statuses.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["fiscal_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fiscal_alerts_company_id"), "fiscal_alerts", ["company_id"], unique=False)
    op.create_index(op.f("ix_fiscal_alerts_obligation_status_id"), "fiscal_alerts", ["obligation_status_id"], unique=False)
    op.create_index(op.f("ix_fiscal_alerts_organization_id"), "fiscal_alerts", ["organization_id"], unique=False)
    op.create_index("ix_fiscal_alerts_org_period_status", "fiscal_alerts", ["organization_id", "period_id", "status"], unique=False)
    op.create_index("ix_fiscal_alerts_org_severity", "fiscal_alerts", ["organization_id", "severity"], unique=False)
    op.create_index(op.f("ix_fiscal_alerts_period_id"), "fiscal_alerts", ["period_id"], unique=False)

    op.create_table(
        "fiscal_installments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.String(length=100), nullable=False),
        sa.Column("protocolo", sa.String(length=100), nullable=True),
        sa.Column("data_adesao", sa.Date(), nullable=True),
        sa.Column("quantidade_parcelas", sa.Integer(), nullable=True),
        sa.Column("parcela_atual", sa.Integer(), nullable=True),
        sa.Column("valor_parcela", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("vencimento", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("ultima_competencia_detectada", sa.String(length=7), nullable=True),
        sa.Column("meses_sem_evidencia", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fiscal_installments_company_id"), "fiscal_installments", ["company_id"], unique=False)
    op.create_index(op.f("ix_fiscal_installments_organization_id"), "fiscal_installments", ["organization_id"], unique=False)
    op.create_index("ix_fiscal_installments_org_company", "fiscal_installments", ["organization_id", "company_id"], unique=False)
    op.create_index("ix_fiscal_installments_org_protocol", "fiscal_installments", ["organization_id", "protocolo"], unique=False)

    op.create_table(
        "integration_sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("integration_account_id", sa.BigInteger(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("run_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["integration_account_id"], ["integration_accounts.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_sync_runs_integration_account_id"), "integration_sync_runs", ["integration_account_id"], unique=False)
    op.create_index(op.f("ix_integration_sync_runs_organization_id"), "integration_sync_runs", ["organization_id"], unique=False)

    op.create_table(
        "watcher_file_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("period_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["external_companies.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["fiscal_periods.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watcher_file_events_company_id"), "watcher_file_events", ["company_id"], unique=False)
    op.create_index("ix_watcher_file_events_file_hash", "watcher_file_events", ["file_hash"], unique=False)
    op.create_index(op.f("ix_watcher_file_events_organization_id"), "watcher_file_events", ["organization_id"], unique=False)
    op.create_index("ix_watcher_file_events_org_status", "watcher_file_events", ["organization_id", "status"], unique=False)
    op.create_index(op.f("ix_watcher_file_events_period_id"), "watcher_file_events", ["period_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_watcher_file_events_period_id"), table_name="watcher_file_events")
    op.drop_index("ix_watcher_file_events_org_status", table_name="watcher_file_events")
    op.drop_index(op.f("ix_watcher_file_events_organization_id"), table_name="watcher_file_events")
    op.drop_index("ix_watcher_file_events_file_hash", table_name="watcher_file_events")
    op.drop_index(op.f("ix_watcher_file_events_company_id"), table_name="watcher_file_events")
    op.drop_table("watcher_file_events")

    op.drop_index(op.f("ix_integration_sync_runs_organization_id"), table_name="integration_sync_runs")
    op.drop_index(op.f("ix_integration_sync_runs_integration_account_id"), table_name="integration_sync_runs")
    op.drop_table("integration_sync_runs")

    op.drop_index("ix_fiscal_installments_org_protocol", table_name="fiscal_installments")
    op.drop_index("ix_fiscal_installments_org_company", table_name="fiscal_installments")
    op.drop_index(op.f("ix_fiscal_installments_organization_id"), table_name="fiscal_installments")
    op.drop_index(op.f("ix_fiscal_installments_company_id"), table_name="fiscal_installments")
    op.drop_table("fiscal_installments")

    op.drop_index(op.f("ix_fiscal_alerts_period_id"), table_name="fiscal_alerts")
    op.drop_index("ix_fiscal_alerts_org_severity", table_name="fiscal_alerts")
    op.drop_index("ix_fiscal_alerts_org_period_status", table_name="fiscal_alerts")
    op.drop_index(op.f("ix_fiscal_alerts_organization_id"), table_name="fiscal_alerts")
    op.drop_index(op.f("ix_fiscal_alerts_obligation_status_id"), table_name="fiscal_alerts")
    op.drop_index(op.f("ix_fiscal_alerts_company_id"), table_name="fiscal_alerts")
    op.drop_table("fiscal_alerts")

    op.drop_index(op.f("ix_fiscal_obligation_statuses_period_id"), table_name="fiscal_obligation_statuses")
    op.drop_index("ix_fiscal_status_org_period_status", table_name="fiscal_obligation_statuses")
    op.drop_index(op.f("ix_fiscal_obligation_statuses_organization_id"), table_name="fiscal_obligation_statuses")
    op.drop_index(op.f("ix_fiscal_obligation_statuses_obligation_id"), table_name="fiscal_obligation_statuses")
    op.drop_index(op.f("ix_fiscal_obligation_statuses_company_id"), table_name="fiscal_obligation_statuses")
    op.drop_table("fiscal_obligation_statuses")

    op.drop_index(op.f("ix_fiscal_evidences_period_id"), table_name="fiscal_evidences")
    op.drop_index("ix_fiscal_evidences_org_period", table_name="fiscal_evidences")
    op.drop_index(op.f("ix_fiscal_evidences_organization_id"), table_name="fiscal_evidences")
    op.drop_index(op.f("ix_fiscal_evidences_company_id"), table_name="fiscal_evidences")
    op.drop_index("ix_fiscal_evidences_file_hash", table_name="fiscal_evidences")
    op.drop_table("fiscal_evidences")

    op.drop_index(op.f("ix_integration_accounts_organization_id"), table_name="integration_accounts")
    op.drop_table("integration_accounts")

    op.drop_index(op.f("ix_fiscal_obligation_rules_organization_id"), table_name="fiscal_obligation_rules")
    op.drop_index(op.f("ix_fiscal_obligation_rules_obligation_id"), table_name="fiscal_obligation_rules")
    op.drop_table("fiscal_obligation_rules")

    op.drop_index(op.f("ix_fiscal_obligations_code"), table_name="fiscal_obligations")
    op.drop_table("fiscal_obligations")

    op.drop_index(op.f("ix_fiscal_periods_organization_id"), table_name="fiscal_periods")
    op.drop_table("fiscal_periods")

    op.drop_index(op.f("ix_company_activity_types_company_id"), table_name="company_activity_types")
    op.drop_table("company_activity_types")

    op.drop_index(op.f("ix_external_companies_organization_id"), table_name="external_companies")
    op.drop_index("ix_external_companies_org_active", table_name="external_companies")
    op.drop_table("external_companies")
