from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class SittaxFiscalDocumentSnapshot(Base):
    __tablename__ = "sittax_fiscal_document_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "sittax_company_snapshot_id",
            "document_direction",
            "source_document_key",
            name="uq_sittax_fdoc_snapshots_org_company_dir_source",
        ),
        Index("ix_sittax_fiscal_document_snapshots_org_period", "organization_id", "fiscal_period_id"),
        Index(
            "ix_sittax_fiscal_document_snapshots_org_external_period",
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
    source_document_key: Mapped[str] = mapped_column(String(255), nullable=False)
    sittax_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    access_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(20), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_reference: Mapped[str] = mapped_column(String(7), nullable=False)
    issuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issuer_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    issuer_document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cfops: Mapped[list[str] | str | None] = mapped_column(JSONB, nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    import_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    imported: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_xml: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
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
