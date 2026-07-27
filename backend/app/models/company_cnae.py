from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class CompanyCnae(Base):
    __tablename__ = "company_cnaes"
    __table_args__ = (
        UniqueConstraint("company_id", "cnae", name="uq_company_cnaes_company_cnae"),
        CheckConstraint("char_length(cnae) = 7 AND cnae ~ '^[0-9]+$'", name="ck_company_cnaes_cnae_digits"),
        Index("ix_company_cnaes_company_active", "company_id", "active"),
        Index("ix_company_cnaes_cnae_active", "cnae", "active"),
        Index(
            "ux_company_cnaes_active_primary_per_company",
            "company_id",
            unique=True,
            postgresql_where=text("active = true and is_primary = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=False, index=True)
    cnae: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    cnae_formatted: Mapped[str] = mapped_column(String(10), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
