from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class EconetCnaeCache(Base):
    __tablename__ = "econet_cnae_cache"
    __table_args__ = (
        UniqueConstraint("cnae", name="uq_econet_cnae_cache_cnae"),
        CheckConstraint("char_length(cnae) = 7 AND cnae ~ '^[0-9]+$'", name="ck_econet_cnae_cache_cnae_digits"),
        CheckConstraint(
            "parse_status IN ('PARSED', 'PARTIAL', 'PARSE_ERROR')",
            name="ck_econet_cnae_cache_parse_status",
        ),
        Index("ix_econet_cnae_cache_econet_id_cnae", "econet_id_cnae"),
        Index("ix_econet_cnae_cache_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cnae: Mapped[str] = mapped_column(String(7), nullable=False)
    cnae_formatted: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    econet_id_cnae: Mapped[str] = mapped_column(String(100), nullable=False)

    activity_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    simples_status: Mapped[str] = mapped_column(String(32), nullable=False)
    simples_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    simples_annex_default: Mapped[str | None] = mapped_column(String(20), nullable=True)
    simples_annex_conditional: Mapped[str | None] = mapped_column(String(20), nullable=True)
    factor_r_applicable: Mapped[bool | None] = mapped_column(nullable=True)
    factor_r_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    mei_status: Mapped[str] = mapped_column(String(32), nullable=False)
    mei_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    mei_occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    presumed_profit_status: Mapped[str] = mapped_column(String(32), nullable=False)
    presumed_profit_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    presumed_profit_irpj_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    presumed_profit_csll_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    actual_profit_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actual_profit_mandatory: Mapped[bool | None] = mapped_column(nullable=True)

    obligations_general: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    obligations_simples: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    obligations_simei: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    unmapped_obligations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
