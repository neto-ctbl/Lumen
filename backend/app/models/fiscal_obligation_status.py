from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalObligationStatus(Base):
    __tablename__ = "fiscal_obligation_statuses"
    __table_args__ = (
        UniqueConstraint("company_id", "period_id", "obligation_id", name="uq_fiscal_status_company_period_obligation"),
        Index("ix_fiscal_status_org_period_status", "organization_id", "period_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=False, index=True)
    period_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=False, index=True)
    obligation_id: Mapped[int] = mapped_column(ForeignKey("fiscal_obligations.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    responsible_department: Mapped[str] = mapped_column(String(30), nullable=False)
    origin_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    main_evidence_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiscal_evidences.id"), nullable=True)
    last_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
