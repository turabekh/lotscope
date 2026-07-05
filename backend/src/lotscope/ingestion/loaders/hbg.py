import json
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.vacancy.derivation import derive_vacancy
from lotscope.valuation.models import Sale
from lotscope.zoning.models import ZoningDistrict

HBG_PARCELS_DATASET = "dc_parcels"
HBG_SALES_DATASET = "dc_deed_references"
HBG_ZONING_DATASET = "tcrp_zoning_districts"
HBG_VACANCY_DATASET = "derived_vacancy"
_MARKET = "hbg"
_LOCAL_SRID = 2272
_HBG_DISTRICT_WHERE = "property_id >= '01' AND property_id < '16'"
_ZONING_SOURCE = "tcrp_zoning"
_ZONING_MUNI_WHERE = "MUNICIPALI LIKE '%HARRISBURG%'"

_PARCEL_FIELDS = (
    "property_i,house_numb,prefix_dir,street_nam,street_suf,post_direc,"
    "land,building,py_used_co,last_name,first_name,org_indi_f,"
    "address1,address2,city,state_code,zip_code"
)
_UPDATE_COLUMNS = [
    "market_code",
    "coverage",
    "address",
    "zip_code",
    "owner",
    "mailing_address",
    "land_use",
    "market_value",
    "land_value",
    "improvement_value",
    "lot_area_sqft",
    "geom_local",
    "geom_4326",
]


def _txt(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if cleaned in ("", "0"):
        return None
    return cleaned


def _owner(props: dict[str, Any]) -> str | None:
    last = _txt(props.get("last_name"))
    if props.get("org_indi_f") == "I":
        first = _txt(props.get("first_name"))
        if last and first:
            return f"{last}, {first}"
    return last


def _situs(props: dict[str, Any]) -> str | None:
    parts = [
        _txt(props.get("house_numb")),
        _txt(props.get("prefix_dir")),
        _txt(props.get("street_nam")),
        _txt(props.get("street_suf")),
        _txt(props.get("post_direc")),
    ]
    joined = " ".join(part for part in parts if part)
    return joined or None


def _mailing(props: dict[str, Any]) -> str | None:
    street = " ".join(
        part for part in (_txt(props.get("address1")), _txt(props.get("address2"))) if part
    )
    locality = ", ".join(
        part for part in (_txt(props.get("city")), _txt(props.get("state_code"))) if part
    )
    zip_code = _txt(props.get("zip_code"))
    if zip_code:
        locality = f"{locality} {zip_code}".strip()
    joined = ", ".join(part for part in (street, locality) if part)
    return joined or None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parcel_row(feature: ArcGisFeature, land_use_names: dict[str, str]) -> dict[str, Any] | None:
    props = feature.properties
    key = get_normalizer(_MARKET).to_canonical(props.get("property_i"))
    if key is None or feature.geometry is None:
        return None
    geom_local = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), _LOCAL_SRID)
    land = _int(props.get("land"))
    building = _int(props.get("building"))
    use_code = _txt(props.get("py_used_co"))
    return {
        "parcel_number": key,
        "market_code": _MARKET,
        "coverage": "full",
        "address": _situs(props),
        "zip_code": _txt(props.get("zip_code")),
        "owner": _owner(props),
        "mailing_address": _mailing(props),
        "land_use": land_use_names.get(use_code) if use_code else None,
        "market_value": (land or 0) + (building or 0) if (land or building) else None,
        "land_value": land,
        "improvement_value": building,
        "lot_area_sqft": func.ST_Area(geom_local),
        "geom_local": geom_local,
        "geom_4326": func.ST_Transform(geom_local, 4326),
    }


async def _fetch_land_use_names(arcgis: ArcGisClient, services_url: str) -> dict[str, str]:
    layer = f"{services_url}/DC_TAX_LANDUSE_CODES/FeatureServer/0/query"
    names: dict[str, str] = {}
    async for features in arcgis.paginate(layer, out_fields="LANDUSE,NAME", page_size=1000):
        for feature in features:
            code = _txt(feature.properties.get("LANDUSE"))
            name = _txt(feature.properties.get("NAME"))
            if code and name:
                names[code] = name
    return names


async def load_hbg_parcels(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    services_url: str,
    municipality: str,
    page_size: int = 2000,
) -> int:
    land_use_names = await _fetch_land_use_names(arcgis, services_url)
    layer = f"{services_url}/DC_Parcels/FeatureServer/0/query"
    where = f"MUNICIPALI = '{municipality}'"
    total = 0
    async for features in arcgis.paginate(
        layer, where=where, out_fields=_PARCEL_FIELDS, out_sr=_LOCAL_SRID, page_size=page_size
    ):
        rows = [
            row for row in (_parcel_row(f, land_use_names) for f in features) if row is not None
        ]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=_UPDATE_COLUMNS,
            )
            total += len(rows)
    await record_freshness(
        session,
        HBG_PARCELS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


async def _hbg_local_keys(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Parcel.local_key).where(Parcel.market_code == _MARKET)
    )
    return set(result.scalars())


def _sale_row(props: dict[str, Any], known_keys: set[str]) -> dict[str, Any] | None:
    local = get_normalizer(_MARKET).normalize_local_key(props.get("property_id"))
    document_id = _txt(props.get("document_number"))
    if local is None or local not in known_keys or document_id is None:
        return None
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "document_id": document_id,
        "document_type": "DEED",
    }


async def load_hbg_sales(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    services_url: str,
    page_size: int = 2000,
) -> int:
    known_keys = await _hbg_local_keys(session)
    layer = f"{services_url}/DC_ParcelCharacteristic/FeatureServer/0/query"
    total = 0
    async for features in arcgis.paginate(
        layer,
        where=_HBG_DISTRICT_WHERE,
        out_fields="property_id,document_number",
        page_size=page_size,
    ):
        rows = [
            row
            for row in (_sale_row(f.properties, known_keys) for f in features)
            if row is not None
        ]
        if rows:
            await upsert(
                session,
                Sale,
                rows,
                index_elements=["parcel_number", "document_id"],
                update_columns=["document_type"],
            )
            total += len(rows)
    await record_freshness(
        session,
        HBG_SALES_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def _district_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    code = _txt(feature.properties.get("MAP_ACRONY"))
    external_id = feature.id if feature.id is not None else feature.properties.get("OBJECTID")
    if feature.geometry is None or code is None or external_id is None:
        return None
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {
        "external_id": f"{_MARKET}:{external_id}",
        "code": code,
        "market_code": _MARKET,
        "geom_4326": geom_4326,
        "geom_local": func.ST_Transform(geom_4326, _LOCAL_SRID),
        "source": _ZONING_SOURCE,
    }


async def load_hbg_zoning_districts(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    services_url: str,
    page_size: int = 2000,
) -> int:
    layer = f"{services_url}/TCRP_CountyZoning_Dauphin/FeatureServer/0/query"
    total = 0
    async for features in arcgis.paginate(
        layer,
        where=_ZONING_MUNI_WHERE,
        page_size=page_size,
    ):
        rows = [
            row for row in (_district_row(f) for f in features) if row is not None
        ]
        if rows:
            await upsert(
                session,
                ZoningDistrict,
                rows,
                index_elements=["external_id"],
                update_columns=["code", "market_code", "geom_local", "geom_4326", "source"],
            )
            total += len(rows)
    await record_freshness(
        session,
        HBG_ZONING_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


_VACANCY_UPDATE = text(
    "UPDATE parcel SET is_vacant = :is_vacant, vacancy_confidence = :conf "
    "WHERE parcel_number = :parcel_number"
)


async def derive_hbg_vacancy(session: AsyncSession) -> int:
    result = await session.execute(
        select(Parcel.parcel_number, Parcel.land_use, Parcel.improvement_value).where(
            Parcel.market_code == _MARKET
        )
    )
    updates: list[dict[str, Any]] = []
    vacant = 0
    for row in result:
        improvement = float(row.improvement_value) if row.improvement_value is not None else None
        is_vacant, confidence = derive_vacancy(row.land_use, improvement)
        updates.append(
            {"parcel_number": row.parcel_number, "is_vacant": is_vacant, "conf": confidence}
        )
        if is_vacant:
            vacant += 1
    if updates:
        await session.execute(_VACANCY_UPDATE, updates)
    await record_freshness(
        session,
        HBG_VACANCY_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=vacant,
    )
    return vacant


HBG_STREETS_DATASET = "dc_streets"
_STREETS_ZIP_WHERE = "ZIPL LIKE '171%' OR ZIPR LIKE '171%'"


def _street_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    if feature.geometry is None or feature.id is None:
        return None
    props = feature.properties
    name_parts = (_txt(props.get("DIRPRE")), _txt(props.get("FEANME")), _txt(props.get("FEATYP")))
    name = " ".join(part for part in name_parts if part)
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {
        "external_id": f"{_MARKET}:{feature.id}",
        "street_name": name or None,
        "street_class": _txt(props.get("CLASS")),
        "market_code": _MARKET,
        "geom_4326": geom_4326,
        "geom_local": func.ST_Transform(geom_4326, _LOCAL_SRID),
        "source": HBG_STREETS_DATASET,
    }


async def load_hbg_streets(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    services_url: str,
    page_size: int = 2000,
) -> int:
    from lotscope.streets.models import StreetCenterline

    layer = f"{services_url}/DC_Streets/FeatureServer/0/query"
    total = 0
    async for features in arcgis.paginate(layer, where=_STREETS_ZIP_WHERE, page_size=page_size):
        rows = [row for row in (_street_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                StreetCenterline,
                rows,
                index_elements=["external_id"],
                update_columns=[
                    "street_name",
                    "street_class",
                    "market_code",
                    "geom_4326",
                    "geom_local",
                    "source",
                ],
            )
            total += len(rows)
    await record_freshness(
        session,
        HBG_STREETS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


HBG_PUBLIC_DATASET = "public_ownership"
_PUBLIC_OWNER_PATTERNS = (
    "CITY OF HARRISBURG",
    "HARRISBURG CITY",
    "REDEVELOPMENT AUTHORITY",
    "HOUSING AUTHORITY",
    "COUNTY OF DAUPHIN",
    "DAUPHIN COUNTY",
    "COMMONWEALTH OF PENNSYLVANIA",
    "LAND BANK",
)


def is_hbg_public_owner(owner: str | None) -> bool:
    if not owner:
        return False
    upper = owner.upper()
    return any(pattern in upper for pattern in _PUBLIC_OWNER_PATTERNS)


_PUBLIC_UPDATE = text(
    "UPDATE parcel SET is_city_owned = :is_public WHERE parcel_number = :parcel_number"
)


async def derive_hbg_public_ownership(session: AsyncSession) -> int:
    result = await session.execute(
        select(Parcel.parcel_number, Parcel.owner).where(Parcel.market_code == _MARKET)
    )
    updates: list[dict[str, Any]] = []
    public = 0
    for row in result:
        is_public = is_hbg_public_owner(row.owner)
        updates.append({"parcel_number": row.parcel_number, "is_public": is_public})
        if is_public:
            public += 1
    if updates:
        await session.execute(_PUBLIC_UPDATE, updates)
    await record_freshness(
        session,
        HBG_PUBLIC_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=public,
    )
    return public
