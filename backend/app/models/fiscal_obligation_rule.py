from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalObligationRule(Base):
    __tablename__ = "fiscal_obligation_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=True, index=True)
    obligation_id: Mapped[int] = mapped_column(ForeignKey("fiscal_obligations.id"), nullable=False, index=True)
    regime: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
