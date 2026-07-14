from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class AcessoriasDeliverySnapshot(Base):
    __tablename__ = "acessorias_delivery_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_company_id",
            "external_delivery_id",
            name="uq_acessorias_delivery_snapshots_org_company_delivery",
        ),
        Index("ix_acessorias_delivery_snapshots_org_company", "organization_id", "company_id"),
        Index("ix_acessorias_delivery_snapshots_org_period", "organization_id", "period_id"),
        Index("ix_acessorias_delivery_snapshots_org_mapping", "organization_id", "obligation_mapping_status"),
        Index("ix_acessorias_delivery_snapshots_org_changed", "organization_id", "external_last_changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=True, index=True)
    period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=True, index=True)
    company_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("acessorias_company_snapshots.id"),
        nullable=True,
        index=True,
    )
    external_company_id: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier: Mapped[str] = mapped_column(String(18), nullable=False)
    external_delivery_id: Mapped[str] = mapped_column(String(100), nullable=False)
    external_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    obligation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    obligation_id: Mapped[int | None] = mapped_column(ForeignKey("fiscal_obligations.id"), nullable=True, index=True)
    obligation_mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    external_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    normalized_status: Mapped[str] = mapped_column(String(50), nullable=False)
    competencia_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    guide_read_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    has_penalty: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    department_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible_deadline_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    responsible_deadline_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible_delivery_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    responsible_delivery_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
