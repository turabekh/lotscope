from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.LOCAL
    log_level: str = "INFO"
    secret_key: str = "change-me-in-env"

    database_url: str = "postgresql+asyncpg://lotscope:lotscope@localhost:5432/lotscope"
    redis_url: str = "redis://localhost:6379/0"
    elasticsearch_url: str = "http://localhost:9200"
    martin_url: str = "http://localhost:3000"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
