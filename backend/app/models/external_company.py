from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ExternalCompany(Base):
    __tablename__ = "external_companies"
    __table_args__ = (
        UniqueConstraint("organization_id", "cnpj", name="uq_external_companies_org_cnpj"),
        Index("ix_external_companies_org_active", "organization_id", "active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    econtrole_company_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    econtrole_profile_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cnpj: Mapped[str] = mapped_column(String(18), nullable=False)
    razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apelido_pasta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    situacao: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inscricao_estadual: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inscricao_municipal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cnae_principal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnaes_secundarios: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    updated_at_econtrole: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at_econtrole: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_econtrole: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
