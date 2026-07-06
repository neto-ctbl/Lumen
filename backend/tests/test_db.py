from sqlalchemy import inspect, text

from backend.app.db.session import create_db_engine


def test_create_db_engine_uses_psycopg_url() -> None:
    engine = create_db_engine("postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test")
    try:
        assert engine.url.drivername == "postgresql+psycopg"
    finally:
        engine.dispose()


def test_audit_log_table_exists(db_session) -> None:
    inspector = inspect(db_session.bind)

    assert "audit_log" in inspector.get_table_names()


def test_test_database_connection_uses_postgres(db_session) -> None:
    database_name = db_session.execute(text("select current_database()")).scalar_one()

    assert database_name == "lumen_test"
