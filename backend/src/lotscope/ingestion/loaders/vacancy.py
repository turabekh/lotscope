from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

VACANCY_DATASET = "vacant_indicators"
VACANCY_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "Vacant_Indicators_Points/FeatureServer/0/query"
)


def to_vacancy_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    parcel_number = normalize_account(
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
        rows = [
            row for row in (to_vacancy_row(feature) for feature in features) if row is not None
        ]
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
