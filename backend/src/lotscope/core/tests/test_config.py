import pytest

from lotscope.core.config import AppEnv, Settings


def test_settings_default_to_local() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env is AppEnv.LOCAL
    assert settings.is_production is False
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s3cret")
    settings = Settings(_env_file=None)
    assert settings.app_env is AppEnv.PRODUCTION
    assert settings.is_production is True
    assert settings.secret_key == "s3cret"
