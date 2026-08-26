from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FactorRAssessment(Base):
    __tablename__ = "factor_r_assessments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_company_id",
            "fiscal_period_id",
            name="uq_factor_r_assessments_org_company_period",
        ),
        Index("ix_factor_r_assessments_org_period", "organization_id", "fiscal_period_id"),
        Index("ix_factor_r_assessments_org_company", "organization_id", "external_company_id"),
        Index("ix_factor_r_assessments_applicability", "applicability_status"),
        Index("ix_factor_r_assessments_reconciliation", "reconciliation_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    external_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("external_companies.id"), nullable=False, index=True
    )
    fiscal_period_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=False, index=True)
    applicability_status: Mapped[str] = mapped_column(String(30), nullable=False)
    calculation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    payroll_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    payroll_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    payroll_months_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    payroll_months_covered: Mapped[int] = mapped_column(Integer, nullable=False)
    payroll_months_with_movement: Mapped[int] = mapped_column(Integer, nullable=False)
    payroll_months_confirmed_zero: Mapped[int] = mapped_column(Integer, nullable=False)
    payroll_months_missing: Mapped[int] = mapped_column(Integer, nullable=False)
    fs12_dominio_estimate: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    fs12_confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    fs12_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rbt12_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    rbt12_source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rbt12_confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    factor_r_estimated_dominio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    estimated_threshold_side: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estimated_annex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    factor_r_sittax_observed: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    sittax_observed_annexes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    factor_r_delta: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
