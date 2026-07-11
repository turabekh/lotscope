from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_REPO_ROOT = _BACKEND_DIR.parent


class AppEnv(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.LOCAL
    git_sha: str = "unknown"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-env"
    access_token_expire_minutes: int = 720

    database_url: str = "postgresql+asyncpg://lotscope:lotscope@localhost:5432/lotscope"
    redis_url: str = "redis://localhost:6379/0"
    martin_url: str = "http://localhost:3000"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_summary_model: str = "claude-haiku-4-5-20251001"

    voyage_api_key: str | None = None
    voyage_url: str = "https://api.voyageai.com/v1/embeddings"
    embedding_model: str = "voyage-3"
    embedding_dimensions: int = 1024
    deed_blob_root: str = "data/deeds"
    philadox_document_url_template: str = (
        "https://epay.phila-records.com/phillyepay/web/integration/document/"
        "InstrumentID={document_id}&Guest=true"
    )

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_from: str = "alerts@parcelphl.online"
    email_from_name: str = "LotScope PHL"
    email_reply_to: str | None = None
    email_allowlist: list[str] = []
    app_base_url: str = "http://localhost:5173"
    api_base_url: str = "http://localhost:8000"
    company_postal_address: str = "LotScope PHL, Philadelphia, PA"

    vapid_private_key: str | None = None
    vapid_public_key: str | None = None
    vapid_subject: str = "mailto:alerts@parcelphl.online"

    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_pro_annual: str | None = None
    stripe_price_pro_legacy: str | None = None
    stripe_price_investor_monthly: str | None = None
    stripe_price_investor_annual: str | None = None
    stripe_price_credits_25: str | None = None
    stripe_price_credits_100: str | None = None
    stripe_price_credits_500: str | None = None
    stripe_price_appeal_packet: str | None = None
    skiptrace_provider: str | None = None
    skiptrace_api_key: str | None = None
    billing_success_url: str = "http://localhost:5173/account?checkout=success"
    billing_cancel_url: str = "http://localhost:5173/account?checkout=cancel"
    billing_portal_return_url: str = "http://localhost:5173/account"
    enterprise_contact_url: str = "mailto:sales@parcelphl.online"

    deal_construction_cost_per_sqft: float = 175.0
    deal_soft_cost_pct: float = 0.15
    deal_selling_cost_pct: float = 0.07
    deal_target_margin: float = 0.20
    deal_default_unit_sqft: float = 1200.0
    deal_max_unit_sqft: float = 3000.0

    google_maps_api_key: str | None = None
    google_map_tiles_url: str = "https://tile.googleapis.com/v1"
    google_viewport_url: str = "https://tile.googleapis.com/tile/v1/viewport"

    carto_sql_url: str = "https://phl.carto.com/api/v2/sql"
    arcgis_hub_url: str = "https://data-phl.opendata.arcgis.com"
    sheriff_sale_csv_path: str | None = None

    rtt_min_sale_date: str = "2005-01-01"
    li_min_event_date: str = "2023-01-01"
    zba_min_decision_date: str = "2019-01-01"

    raw_retention_days: int = 90
    event_retention_months: int = 18

    http_timeout_seconds: float = 30.0
    http_max_retries: int = 3
    http_backoff_seconds: float = 0.5

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
