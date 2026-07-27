from backend.app.core.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_TEST_DATABASE_URL,
    REPO_ROOT,
    Settings,
    get_settings,
)


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


def test_get_settings_reloads_when_tracked_env_changes(monkeypatch) -> None:
    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "false")
    get_settings.cache_clear()
    assert get_settings().econet_assisted_session_enabled is False

    monkeypatch.setenv("ECONET_ASSISTED_SESSION_ENABLED", "true")
    assert get_settings().econet_assisted_session_enabled is True
    get_settings.cache_clear()


def test_get_settings_reloads_when_env_file_changes(monkeypatch) -> None:
    monkeypatch.delenv("ECONET_ASSISTED_SESSION_ENABLED", raising=False)
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    original = env_path.read_text(encoding="utf-8")
    get_settings.cache_clear()
    try:
        if "ECONET_ASSISTED_SESSION_ENABLED=true" in original:
            replacement = original.replace("ECONET_ASSISTED_SESSION_ENABLED=true", "ECONET_ASSISTED_SESSION_ENABLED=false", 1)
            expected = False
        elif "ECONET_ASSISTED_SESSION_ENABLED=false" in original:
            replacement = original.replace("ECONET_ASSISTED_SESSION_ENABLED=false", "ECONET_ASSISTED_SESSION_ENABLED=true", 1)
            expected = True
        else:
            replacement = original.rstrip() + "\nECONET_ASSISTED_SESSION_ENABLED=true\n"
            expected = True

        env_path.write_text(replacement, encoding="utf-8")
        assert get_settings().econet_assisted_session_enabled is expected
    finally:
        env_path.write_text(original, encoding="utf-8")
        get_settings.cache_clear()
