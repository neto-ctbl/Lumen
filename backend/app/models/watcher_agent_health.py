from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class WatcherAgentHealth(Base):
    """Latest sanitized heartbeat for one organization, not a run history."""

    __tablename__ = "watcher_agent_health"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_watcher_agent_health_organization"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("organizations.id"), nullable=False, index=True)
    reported_status: Mapped[str] = mapped_column(String(20), nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_last_successful_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    counters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
