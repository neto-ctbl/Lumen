from __future__ import annotations

from collections.abc import Generator
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import DEFAULT_TEST_DATABASE_URL, Settings, get_settings


def _admin_url(url: URL) -> URL:
    return url.set(database="postgres")


def _quoted_db_name(url: URL) -> str:
    assert url.database is not None
    return '"' + url.database.replace('"', '""') + '"'


def ensure_test_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    admin_engine = create_engine(_admin_url(url), isolation_level="AUTOCOMMIT", future=True)
    db_name = _quoted_db_name(url)
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f"CREATE DATABASE {db_name}"))
    finally:
        admin_engine.dispose()


def drop_test_database_objects(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    os.environ.pop("TEST_DATABASE_URL", None)
    os.environ["LUMEN_TEST_DATABASE_URL"] = DEFAULT_TEST_DATABASE_URL
    os.environ["DATABASE_URL"] = DEFAULT_TEST_DATABASE_URL
    get_settings.cache_clear()
    return Settings()


@pytest.fixture(scope="session")
def alembic_config(test_settings: Settings) -> Config:
    config = Config("backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", test_settings.test_database_url)
    return config


@pytest.fixture(scope="session")
def prepared_test_database(test_settings: Settings, alembic_config: Config) -> Generator[None, None, None]:
    ensure_test_database_exists(test_settings.test_database_url)
    drop_test_database_objects(test_settings.test_database_url)
    command.upgrade(alembic_config, "head")
    yield
    command.downgrade(alembic_config, "base")
    drop_test_database_objects(test_settings.test_database_url)


@pytest.fixture()
def db_session(test_settings: Settings, prepared_test_database: None) -> Generator[Session, None, None]:
    engine = create_engine(test_settings.test_database_url, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    with engine.connect() as connection:
        transaction = connection.begin()
        session = session_factory(bind=connection)
        try:
            yield session
        finally:
            session.close()
            if transaction.is_active:
                transaction.rollback()
    engine.dispose()
