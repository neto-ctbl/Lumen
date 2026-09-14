from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class FiscalDocumentParserRun(Base):
    __tablename__ = "fiscal_document_parser_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "fiscal_evidence_id",
            "parser_name",
            "parser_version",
            name="uq_fiscal_doc_parser_runs_org_evidence_parser_version",
        ),
        CheckConstraint(
            "extraction_status IN ('MATCHED', 'UNSUPPORTED', 'INCONCLUSIVE', 'INVALID', 'ERROR')",
            name="ck_fiscal_doc_parser_runs_extraction_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_fiscal_doc_parser_runs_confidence",
        ),
        Index("ix_fiscal_doc_parser_runs_org_evidence", "organization_id", "fiscal_evidence_id"),
        Index("ix_fiscal_doc_parser_runs_org_status", "organization_id", "extraction_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fiscal_evidence_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fiscal_evidences.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    document_family: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
