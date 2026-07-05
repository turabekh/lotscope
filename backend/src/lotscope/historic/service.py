from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.historic.schemas import HistoricResult

HISTORIC_REVIEW_NOTE = (
    "Exterior alterations, demolition, and new construction require Philadelphia Historical "
    "Commission review, which adds time and cost. Informational — confirm with the Commission."
)

_PARCEL_SQL = text(
    "SELECT (geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_HISTORIC_SQL = text(
    "SELECT hd.name, hd.designated_date FROM parcel p "
    "JOIN historic_district hd ON hd.market_code = p.market_code "
    "AND ST_Intersects(hd.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL "
    "ORDER BY hd.name LIMIT 1"
)

_SOURCES: list[dict[str, Any]] = [{"source": "historicdistricts_local"}]


async def get_parcel_historic(session: AsyncSession, parcel_number: str) -> HistoricResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    computed_at = datetime.now(UTC)

    row = None
    if parcel.has_geometry:
        row = (await session.execute(_HISTORIC_SQL, {"parcel_number": parcel_number})).one_or_none()

    in_district = row is not None
    return HistoricResult(
        parcel_number=parcel_number,
        in_historic_district=in_district,
        district_name=row.name if row is not None else None,
        designated_date=row.designated_date if row is not None else None,
        note=HISTORIC_REVIEW_NOTE if in_district else None,
        sources=_SOURCES,
        computed_at=computed_at,
    )
