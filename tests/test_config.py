from collections.abc import Iterator

import pytest

from fsp_market.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    """get_settings is cached; never leak an overridden instance into other test modules."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_NAME", raising=False)
    get_settings.cache_clear()

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://fsp:change-me@localhost:5432/fsp_market"
    assert settings.jwt_secret == "dev-only-secret"
    assert settings.environment == "local"
    assert settings.app_name == "FSP Talent Market"


def test_database_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@localhost:5432/c")
    get_settings.cache_clear()

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://a:b@localhost:5432/c"


def test_get_settings_returns_same_object() -> None:
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second


def test_get_settings_cache_clear_with_app_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Other")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Other"
