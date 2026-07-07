from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.organization import Organization
    from backend.app.models.user_organization import UserOrganization


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    global_role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    default_organization_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("organizations.id"),
        nullable=True,
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_logout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    default_organization: Mapped["Organization | None"] = relationship(foreign_keys=[default_organization_id])
    organizations: Mapped[list["UserOrganization"]] = relationship(back_populates="user")

    @validates("email")
    def normalize_email(self, _: str, value: str) -> str:
        return value.strip().lower()

    @validates("global_role")
    def normalize_role(self, _: str, value: str) -> str:
        return value.strip().upper()
