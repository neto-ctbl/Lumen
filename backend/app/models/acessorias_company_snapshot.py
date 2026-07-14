from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class AcessoriasCompanySnapshot(Base):
    __tablename__ = "acessorias_company_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_company_id", name="uq_acessorias_company_snapshots_org_external"),
        Index("ix_acessorias_company_snapshots_org_identifier", "organization_id", "identifier"),
        Index("ix_acessorias_company_snapshots_org_company", "organization_id", "company_id"),
        Index("ix_acessorias_company_snapshots_org_regime", "organization_id", "regime_canonical"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    company_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("external_companies.id"), nullable=True, index=True)
    external_company_id: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier: Mapped[str] = mapped_column(String(18), nullable=False)
    razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    regime_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regime_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regime_canonical: Mapped[str | None] = mapped_column(String(100), nullable=True)
    regime_mapping_status: Mapped[str] = mapped_column(String(20), nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
