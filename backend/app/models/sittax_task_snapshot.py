from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SittaxTaskSnapshot(Base):
    __tablename__ = "sittax_task_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_task_key", name="uq_sittax_task_snapshots_org_source_key"),
        Index("ix_sittax_task_snapshots_org_period", "organization_id", "fiscal_period_id"),
        Index("ix_sittax_task_snapshots_org_external_period", "organization_id", "external_company_id", "fiscal_period_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    source_task_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sittax_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sittax_company_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("sittax_company_snapshots.id"),
        nullable=True,
        index=True,
    )
    external_company_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("external_companies.id"),
        nullable=True,
        index=True,
    )
    fiscal_period_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("fiscal_periods.id"), nullable=True, index=True)
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    period_reference: Mapped[str | None] = mapped_column(String(7), nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status_code: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    has_file: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_extension_code: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    processing_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
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
