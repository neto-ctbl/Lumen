from backend.app.core.config import DEFAULT_DATABASE_URL, DEFAULT_TEST_DATABASE_URL, Settings


def test_settings_load_database_urls_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://example:example@localhost:5435/example")
    monkeypatch.setenv("LUMEN_TEST_DATABASE_URL", "postgresql+psycopg://example:example@localhost:5435/example_test")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://example:example@localhost:5435/example"
    assert settings.test_database_url == "postgresql+psycopg://example:example@localhost:5435/example_test"


def test_settings_defaults_match_project_contract(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("LUMEN_TEST_DATABASE_URL", raising=False)

    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.test_database_url == DEFAULT_TEST_DATABASE_URL
