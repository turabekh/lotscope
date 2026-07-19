import json
from typing import Any, cast

from sqlalchemy import CursorResult, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.historic.models import HistoricDistrict
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import FloodZone
from lotscope.zoning.models import ZoningOverlay

_MARKET = "wlm"
_SRID = 2235
_LUP = "LUP_Map_w_RISE_STAR_Bldg_Code_Enf_and_DDD_WFL1/FeatureServer"
_LANDBANK_LAYER = "LandBankSideLotParcels_Web_WilmDE/FeatureServer/0"

WLM_FLOOD_DATASET = "wilmington_flood"
WLM_HISTORIC_DATASET = "wilmington_historic"
WLM_OVERLAYS_DATASET = "wilmington_overlays"
WLM_PUBLIC_DATASET = "wilmington_public"


def _txt(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _lup_layer(arcgis_base_url: str, layer_id: int) -> str:
    return f"{arcgis_base_url.rstrip('/')}/{_LUP}/{layer_id}"


def _geom_local(feature: ArcGisFeature) -> Any:
    return func.ST_MakeValid(
        func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), _SRID)
    )


def to_wlm_flood_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    prclid = _txt(feature.properties.get("PRCLID"))
    if feature.geometry is None or not prclid:
        return None
    geom_local = _geom_local(feature)
    return {
        "external_id": f"wlm-flood-{prclid}",
        "zone": _txt(feature.properties.get("FloodHaz")),
        "market_code": _MARKET,
        "geom_local": geom_local,
        "geom_4326": func.ST_Transform(geom_local, 4326),
        "source": WLM_FLOOD_DATASET,
    }


async def load_wlm_flood(
    session: AsyncSession, arcgis: ArcGisClient, *, arcgis_base_url: str, page_size: int = 2000
) -> int:
    layer = f"{_lup_layer(arcgis_base_url, 10)}/query"
    total = 0
    async for features in arcgis.paginate(
        layer, out_fields="PRCLID,FloodHaz", out_sr=_SRID, page_size=page_size
    ):
        rows = [row for row in (to_wlm_flood_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                FloodZone,
                rows,
                index_elements=["external_id"],
                update_columns=["zone", "market_code", "geom_local", "geom_4326", "source"],
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_FLOOD_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def to_wlm_historic_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    prclid = _txt(feature.properties.get("PRCLID"))
    name = _txt(feature.properties.get("HistoricC"))
    if feature.geometry is None or not prclid or not name:
        return None
    geom_local = _geom_local(feature)
    return {
        "external_id": f"wlm-hist-{prclid}",
        "name": name,
        "market_code": _MARKET,
        "geom_local": geom_local,
        "geom_4326": func.ST_Transform(geom_local, 4326),
        "source": WLM_HISTORIC_DATASET,
    }


async def load_wlm_historic(
    session: AsyncSession, arcgis: ArcGisClient, *, arcgis_base_url: str, page_size: int = 2000
) -> int:
    layer = f"{_lup_layer(arcgis_base_url, 3)}/query"
    total = 0
    async for features in arcgis.paginate(
        layer, out_fields="PRCLID,HistoricC", out_sr=_SRID, page_size=page_size
    ):
        rows = [row for row in (to_wlm_historic_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                HistoricDistrict,
                rows,
                index_elements=["external_id"],
                update_columns=["name", "market_code", "geom_local", "geom_4326", "source"],
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_HISTORIC_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def _overlay_row(
    feature: ArcGisFeature, *, external_id: str, code: str, name: str
) -> dict[str, Any]:
    geom_local = _geom_local(feature)
    return {
        "external_id": external_id,
        "code": code,
        "name": name,
        "code_section": "Wilmington Ch. 48 (DDD/RISE)",
        "market_code": _MARKET,
        "geom_local": geom_local,
        "geom_4326": func.ST_Transform(geom_local, 4326),
        "source": WLM_OVERLAYS_DATASET,
    }


async def load_wlm_overlays(
    session: AsyncSession, arcgis: ArcGisClient, *, arcgis_base_url: str, page_size: int = 2000
) -> int:
    _overlay_columns = [
        "code",
        "name",
        "code_section",
        "market_code",
        "geom_local",
        "geom_4326",
        "source",
    ]
    total = 0
    async for features in arcgis.paginate(
        f"{_lup_layer(arcgis_base_url, 23)}/query",
        out_fields="OBJECTID,Area_Name",
        out_sr=_SRID,
        page_size=page_size,
    ):
        rows = []
        for feature in features:
            if feature.geometry is None:
                continue
            area = _txt(feature.properties.get("Area_Name"))
            rows.append(
                _overlay_row(
                    feature,
                    external_id=f"wlm-rise-{feature.properties.get('OBJECTID')}",
                    code="RISE-STAR",
                    name=f"RISE-STAR incentive area{f' ({area})' if area else ''}",
                )
            )
        if rows:
            await upsert(
                session,
                ZoningOverlay,
                rows,
                index_elements=["external_id"],
                update_columns=_overlay_columns,
            )
            total += len(rows)
    async for features in arcgis.paginate(
        f"{_lup_layer(arcgis_base_url, 25)}/query",
        out_fields="OBJECTID",
        out_sr=_SRID,
        page_size=page_size,
    ):
        rows = [
            _overlay_row(
                feature,
                external_id=f"wlm-ddd-{feature.properties.get('OBJECTID')}",
                code="DDD",
                name="Downtown Development District",
            )
            for feature in features
            if feature.geometry is not None
        ]
        if rows:
            await upsert(
                session,
                ZoningOverlay,
                rows,
                index_elements=["external_id"],
                update_columns=_overlay_columns,
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_OVERLAYS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


async def load_wlm_public(
    session: AsyncSession, arcgis: ArcGisClient, *, arcgis_base_url: str, page_size: int = 2000
) -> int:
    layer = f"{arcgis_base_url.rstrip('/')}/{_LANDBANK_LAYER}/query"
    normalizer = get_normalizer(_MARKET)
    keys: set[str] = set()
    async for features in arcgis.paginate(
        layer,
        out_fields="L0NCC_REST_Parcel_Data_PRCLID",
        return_geometry=False,
        page_size=page_size,
    ):
        for feature in features:
            key = normalizer.to_canonical(feature.properties.get("L0NCC_REST_Parcel_Data_PRCLID"))
            if key is not None:
                keys.add(key)
    count = 0
    if keys:
        executed = await session.execute(
            update(Parcel).where(Parcel.parcel_number.in_(keys)).values(is_city_owned=True)
        )
        count = cast("CursorResult[Any]", executed).rowcount or 0
    await record_freshness(
        session,
        WLM_PUBLIC_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=count,
    )
    return count
