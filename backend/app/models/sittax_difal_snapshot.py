from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SittaxDifalSnapshot(Base):
    __tablename__ = "sittax_difal_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "fiscal_period_id",
            name="uq_sittax_difal_snapshots_org_company_period",
        ),
        Index("ix_sittax_difal_snapshots_org_period", "organization_id", "fiscal_period_id"),
        Index("ix_sittax_difal_snapshots_org_external_period", "organization_id", "external_company_id", "fiscal_period_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    sittax_company_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sittax_company_snapshots.id"),
        nullable=False,
        index=True,
    )
    sittax_apuracao_snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sittax_apuracao_snapshots.id"),
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
    company_cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    period_reference: Mapped[str] = mapped_column(String(7), nullable=False)
    has_guide: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dare_numbers: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    resale_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    use_consumption_fixed_asset_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transmission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_purchases: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes_without_type_or_reference: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    inconsistencies: Mapped[list[dict[str, Any] | str] | None] = mapped_column(JSONB, nullable=True)
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
