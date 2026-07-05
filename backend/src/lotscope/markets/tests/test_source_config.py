from lotscope.core.config import Settings
from lotscope.markets.seed import market_source_url


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        carto_sql_url="https://settings.example/sql",
        arcgis_hub_url="https://settings.example/arcgis",
    )


def test_source_config_value_takes_precedence() -> None:
    config = {"carto_sql_url": "https://market.example/sql"}
    assert market_source_url(config, "carto_sql_url", _settings()) == "https://market.example/sql"


def test_falls_back_to_settings_when_missing() -> None:
    assert market_source_url({}, "carto_sql_url", _settings()) == "https://settings.example/sql"
    assert (
        market_source_url({}, "arcgis_hub_url", _settings()) == "https://settings.example/arcgis"
    )
