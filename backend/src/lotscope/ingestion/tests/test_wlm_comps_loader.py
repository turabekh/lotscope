from datetime import date

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.wlm import load_wlm_comps, to_wlm_sale_row

_LAYER_URL = "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services/LUP/FeatureServer/0"


def test_sale_row_pivots_two_digit_year_and_uses_month() -> None:
    row = to_wlm_sale_row(
        ArcGisFeature(
            properties={"PRCLID": "2601320063", "SALEPRC": 195000, "SALEYR": 12, "SALEMON": 3}
        )
    )
    assert row is not None
    assert row["parcel_number"] == "wlm:2601320063"
    assert row["sale_price"] == 195000.0
    assert row["sale_date"] == date(2012, 3, 1)
    assert row["document_id"] == "wlm_assessment_last_sale"


def test_sale_row_maps_old_century_and_unknown_month_to_january() -> None:
    row = to_wlm_sale_row(
        ArcGisFeature(
            properties={"PRCLID": "2601320063", "SALEPRC": 60000, "SALEYR": 85, "SALEMON": 0}
        )
    )
    assert row is not None
    assert row["sale_date"] == date(1985, 1, 1)


def test_sale_row_skips_ambiguous_year_zero_and_missing_price() -> None:
    assert (
        to_wlm_sale_row(
            ArcGisFeature(properties={"PRCLID": "2601320063", "SALEPRC": 50000, "SALEYR": 0})
        )
        is None
    )
    assert (
        to_wlm_sale_row(
            ArcGisFeature(properties={"PRCLID": "2601320063", "SALEPRC": 0, "SALEYR": 12})
        )
        is None
    )


class _CompsHandler:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.calls > 1:
            return httpx.Response(200, json={"type": "FeatureCollection", "features": []})
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": None,
                        "properties": {
                            "PRCLID": "2601320063",
                            "SALEPRC": 195000,
                            "SALEYR": 12,
                            "SALEMON": 3,
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": None,
                        "properties": {
                            "PRCLID": "9999999999",
                            "SALEPRC": 111,
                            "SALEYR": 5,
                            "SALEMON": 1,
                        },
                    },
                ],
            },
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_wlm_comps_writes_sale_for_known_parcel_only_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES ('wlm:2601320063', 'wlm')")
    )
    await db_session.flush()

    for _ in range(2):
        async with ArcGisClient(
            _settings(), transport=httpx.MockTransport(_CompsHandler())
        ) as arcgis:
            total = await load_wlm_comps(db_session, arcgis, parcels_layer_url=_LAYER_URL)
        await db_session.flush()
        assert total == 1

    rows = (
        await db_session.execute(
            text(
                "SELECT parcel_number, sale_price, sale_date, document_type "
                "FROM sale WHERE parcel_number = 'wlm:2601320063'"
            )
        )
    ).all()
    assert len(rows) == 1
    assert float(rows[0][1]) == 195000.0
    assert rows[0][2] == date(2012, 3, 1)
    assert rows[0][3] == "assessment_last_sale"

    orphan = await db_session.scalar(
        text("SELECT count(*) FROM sale WHERE parcel_number = 'wlm:9999999999'")
    )
    assert orphan == 0
