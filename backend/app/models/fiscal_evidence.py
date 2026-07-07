from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalEvidence(Base):
    __tablename__ = "fiscal_evidences"
    __table_args__ = (
        Index("ix_fiscal_evidences_org_period", "organization_id", "period_id"),
        Index("ix_fiscal_evidences_file_hash", "file_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=True, index=True)
    period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_tax: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detected_obligation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cnpj_detected: Mapped[str | None] = mapped_column(String(18), nullable=True)
    ie_detected: Mapped[str | None] = mapped_column(String(50), nullable=True)
    razao_social_detected: Mapped[str | None] = mapped_column(String(255), nullable=True)
    competencia_detected: Mapped[str | None] = mapped_column(String(7), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount_principal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount_multa: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount_juros: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(255), nullable=True)
    installment_protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
    installment_current: Mapped[int | None] = mapped_column(nullable=True)
    installment_total: Mapped[int | None] = mapped_column(nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="PENDENTE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
