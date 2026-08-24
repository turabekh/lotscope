from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.vacancy.derivation import derive_vacancy

VACANCY_DATASET = "vacant_indicators"
DERIVED_VACANCY_DATASET = "opa_derived_vacancy"
_MARKET = "phl"

_DERIVED_VACANCY_UPDATE = text(
    "UPDATE parcel SET is_vacant = true, vacancy_confidence = :conf "
    "WHERE parcel_number = :parcel_number AND coalesce(is_vacant, false) = false"
)
VACANCY_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "Vacant_Indicators_Points/FeatureServer/0/query"
)


def to_vacancy_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(
        first_present(
            feature.properties,
            "OPA_ID",
            "opa_id",
            "OPA_ACCOUNT_NUM",
            "opa_account_num",
            "PARCEL",
        )
    )
    if parcel_number is None:
        return None
    return {"parcel_number": parcel_number, "is_vacant": True, "source": VACANCY_DATASET}


async def load_vacancy(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = VACANCY_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [row for row in (to_vacancy_row(feature) for feature in features) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=["is_vacant", "source"],
            )
            total += len(rows)
    await record_freshness(
        session, VACANCY_DATASET, status="success", success=True, row_count=total
    )
    return total


async def derive_phl_vacancy(session: AsyncSession) -> int:
    result = await session.execute(
        select(Parcel.parcel_number, Parcel.land_use, Parcel.improvement_value).where(
            Parcel.market_code == _MARKET,
            Parcel.is_vacant.is_not(True),
        )
    )
    updates: list[dict[str, Any]] = []
    for row in result:
        improvement = float(row.improvement_value) if row.improvement_value is not None else None
        is_vacant, confidence = derive_vacancy(row.land_use, improvement, _MARKET)
        if is_vacant:
            updates.append({"parcel_number": row.parcel_number, "conf": confidence})
    if updates:
        await session.execute(_DERIVED_VACANCY_UPDATE, updates)
    await record_freshness(
        session,
        DERIVED_VACANCY_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=len(updates),
    )
    return len(updates)
