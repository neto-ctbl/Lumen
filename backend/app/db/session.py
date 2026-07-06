from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    return create_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
