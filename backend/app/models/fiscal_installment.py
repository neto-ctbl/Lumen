from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalInstallment(Base):
    __tablename__ = "fiscal_installments"
    __table_args__ = (
        Index("ix_fiscal_installments_org_company", "organization_id", "company_id"),
        Index("ix_fiscal_installments_org_protocol", "organization_id", "protocolo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    protocolo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_adesao: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantidade_parcelas: Mapped[int | None] = mapped_column(nullable=True)
    parcela_atual: Mapped[int | None] = mapped_column(nullable=True)
    valor_parcela: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    vencimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    ultima_competencia_detectada: Mapped[str | None] = mapped_column(String(7), nullable=True)
    meses_sem_evidencia: Mapped[int | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
