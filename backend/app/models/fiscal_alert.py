from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalAlert(Base):
    __tablename__ = "fiscal_alerts"
    __table_args__ = (
        Index("ix_fiscal_alerts_org_period_status", "organization_id", "period_id", "status"),
        Index("ix_fiscal_alerts_org_severity", "organization_id", "severity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=True, index=True)
    period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=True, index=True)
    obligation_status_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("fiscal_obligation_statuses.id"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    department: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="OPEN")
    rule_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
