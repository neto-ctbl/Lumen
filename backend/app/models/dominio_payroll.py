from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class DominioPayrollImportStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"


class DominioPayrollMatchStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    INVALID_CNPJ = "INVALID_CNPJ"
    MISSING_CNPJ = "MISSING_CNPJ"
    AMBIGUOUS = "AMBIGUOUS"


class DominioPayrollImport(Base):
    __tablename__ = "dominio_payroll_imports"
    __table_args__ = (
        UniqueConstraint("organization_id", "file_sha256", name="uq_dominio_payroll_imports_org_sha256"),
        Index("ix_dominio_payroll_imports_org_imported", "organization_id", "imported_at"),
        Index("ix_dominio_payroll_imports_org_status", "organization_id", "status"),
        Index("ix_dominio_payroll_imports_file_sha256", "file_sha256"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    assessment_period_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("fiscal_periods.id"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(50), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    selection_scope: Mapped[str] = mapped_column(String(30), nullable=False, server_default="UNKNOWN")
    source_filter_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_list_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_competences: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    assessment_competences: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_companies: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_matched: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_unmatched: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_invalid_cnpj: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_missing_cnpj: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_ambiguous: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_warnings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DominioPayrollCompanyMovement(Base):
    __tablename__ = "dominio_payroll_company_movements"
    __table_args__ = (
        UniqueConstraint("import_id", "source_company_key", name="uq_dominio_payroll_movements_import_company_key"),
        Index("ix_dominio_payroll_movements_org_match_status", "organization_id", "match_status"),
        Index("ix_dominio_payroll_movements_org_period", "organization_id", "fiscal_period_id"),
        Index("ix_dominio_payroll_movements_movement_hash", "movement_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    import_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dominio_payroll_imports.id"), nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    external_company_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("external_companies.id"),
        nullable=True,
        index=True,
    )
    fiscal_period_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("fiscal_periods.id"),
        nullable=True,
        index=True,
    )
    source_company_key: Mapped[str] = mapped_column(String(255), nullable=False)
    dominio_company_code: Mapped[str] = mapped_column(String(50), nullable=False)
    company_cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True)
    source_company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_payroll_competence: Mapped[date | None] = mapped_column(Date, nullable=True)
    assessment_competence: Mapped[date | None] = mapped_column(Date, nullable=True)
    match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    parser_confidence: Mapped[str] = mapped_column(String(30), nullable=False)
    calculation_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_payroll: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_employee: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_pro_labore: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_autonomous: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_inss: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_fgts: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_termination: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_vacation: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    has_leave: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    gross_total: Mapped[Any | None] = mapped_column(Numeric(14, 2), nullable=True)
    discount_total: Mapped[Any | None] = mapped_column(Numeric(14, 2), nullable=True)
    informative_total: Mapped[Any | None] = mapped_column(Numeric(14, 2), nullable=True)
    net_total: Mapped[Any | None] = mapped_column(Numeric(14, 2), nullable=True)
    source_page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_page_numbers: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    declared_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movement_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rubrics_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
