from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SittaxApuracaoSnapshot(Base):
    __tablename__ = "sittax_apuracao_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "fiscal_period_id",
            name="uq_sittax_apuracao_snapshots_org_company_period",
        ),
        Index("ix_sittax_apuracao_snapshots_org_period", "organization_id", "fiscal_period_id"),
        Index(
            "ix_sittax_apuracao_snapshots_org_external_period",
            "organization_id",
            "external_company_id",
            "fiscal_period_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    sittax_company_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sittax_company_snapshots.id"),
        nullable=False,
        index=True,
    )
    external_company_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("external_companies.id"),
        nullable=True,
        index=True,
    )
    fiscal_period_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=False, index=True)
    sittax_apuracao_id: Mapped[str] = mapped_column(String(100), nullable=False)
    company_cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_reference: Mapped[str] = mapped_column(String(7), nullable=False)
    is_transmitted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transmission_in_progress: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transmission_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transmitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    net_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    product_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    service_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    return_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rbt12: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rba: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    das_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    das_xml_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    factor_r_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    company_has_payroll: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    taxes_icms: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    taxes_iss: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    taxes_ipi: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    taxes_pis_cofins: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    companies_apuracao: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    annexes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    cfops: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    activities: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    payrolls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    alerts: Mapped[list[dict[str, Any] | str] | None] = mapped_column(JSONB, nullable=True)
    errors: Mapped[list[dict[str, Any] | str] | None] = mapped_column(JSONB, nullable=True)
    risks: Mapped[list[dict[str, Any] | str] | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
