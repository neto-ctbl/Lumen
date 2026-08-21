from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class DctfwebExpectedOrigin(str, Enum):
    DP = "DP"
    FISCAL = "FISCAL"
    COMPARTILHADO = "COMPARTILHADO"
    UNDETERMINED = "UNDETERMINED"


class DctfwebDpCoverageStatus(str, Enum):
    CONFIRMED_MOVEMENT = "CONFIRMED_MOVEMENT"
    CONFIRMED_NO_MOVEMENT = "CONFIRMED_NO_MOVEMENT"
    REPORT_MISSING = "REPORT_MISSING"


class DctfwebClassificationConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DctfwebOriginAssessment(Base):
    __tablename__ = "dctfweb_origin_assessments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_company_id",
            "fiscal_period_id",
            name="uq_dctfweb_origin_assessments_org_company_period",
        ),
        Index("ix_dctfweb_origin_assessments_org_period", "organization_id", "fiscal_period_id"),
        Index("ix_dctfweb_origin_assessments_org_company", "organization_id", "external_company_id"),
        Index("ix_dctfweb_origin_assessments_origin", "expected_origin"),
        Index("ix_dctfweb_origin_assessments_department", "expected_responsible_department"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    external_company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("external_companies.id"), nullable=False, index=True
    )
    fiscal_period_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=False, index=True)
    assessment_competence: Mapped[date] = mapped_column(Date, nullable=False)
    source_payroll_competence: Mapped[date | None] = mapped_column(Date, nullable=True)
    dp_coverage_status: Mapped[str] = mapped_column(String(30), nullable=False)
    dp_signal_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reinf_signal_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    mit_signal_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fiscal_signal_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dctfweb_observed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected_origin: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_responsible_department: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification_confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
