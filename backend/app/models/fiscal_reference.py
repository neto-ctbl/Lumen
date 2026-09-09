from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalReferenceDataset(Base):
    __tablename__ = "fiscal_reference_datasets"
    __table_args__ = (
        UniqueConstraint(
            "source_kind",
            "file_sha256",
            "parser_version",
            name="uq_fiscal_reference_datasets_kind_sha256_parser",
        ),
        Index("ix_fiscal_reference_datasets_source_kind", "source_kind"),
        Index(
            "ux_fiscal_reference_datasets_one_active_kind",
            "source_kind",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    rows_imported: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    import_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FiscalReferenceEntry(Base):
    __tablename__ = "fiscal_reference_entries"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "source_sheet", "source_row_number", "source_kind",
            name="uq_fiscal_reference_entries_physical_row",
        ),
        Index("ix_fiscal_reference_entries_dataset_id", "dataset_id"),
        Index("ix_fiscal_reference_entries_source_kind", "source_kind"),
        Index("ix_fiscal_reference_entries_cnae", "cnae"),
        Index("ix_fiscal_reference_entries_lc116_item", "lc116_item"),
        Index("ix_fiscal_reference_entries_nbs", "nbs"),
        Index("ix_fiscal_reference_entries_trib_nac_code", "trib_nac_code"),
        Index("ix_fiscal_reference_entries_class_trib_code", "class_trib_code"),
        Index("ix_fiscal_reference_entries_cst_code", "cst_code"),
        Index("ix_fiscal_reference_entries_indop_code", "indop_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("fiscal_reference_datasets.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cnae: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnae_formatted: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnae_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lc116_item: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lc116_item_formatted: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lc116_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    iss_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    allows_tax_outside: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lc116_inciso: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trib_nac_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trib_nac_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nbs: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nbs_formatted: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nbs_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_trib_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    class_trib_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cst_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cst_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    indop_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    indop_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    onerous: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    foreign_acquisition: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ibs_incidence_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
