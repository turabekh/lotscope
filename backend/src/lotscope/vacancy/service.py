from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.vacancy.scoring import VacancySignals, vacancy_confidence

_BULK_SIGNALS_SQL = text(
    "SELECT p.parcel_number, p.is_vacant, p.improvement_value, p.land_value, "
    "coalesce(li.vacancy_violations, 0) AS vacancy_violations, "
    "coalesce(li.demolitions, 0) AS demolitions, "
    "coalesce(li.recent_permits, 0) AS recent_permits "
    "FROM parcel p "
    "LEFT JOIN ("
    "  SELECT parcel_number, "
    "  count(*) FILTER ("
    "    WHERE event_type = 'violation' AND upper(coalesce(description, '')) LIKE '%VACANT%'"
    "  ) AS vacancy_violations, "
    "  count(*) FILTER (WHERE event_type = 'demolition') AS demolitions, "
    "  count(*) FILTER ("
    "    WHERE event_type = 'permit' AND event_date >= (CURRENT_DATE - INTERVAL '2 years')"
    "  ) AS recent_permits "
    "  FROM li_event WHERE parcel_number = ANY(:parcel_numbers) GROUP BY parcel_number"
    ") li ON li.parcel_number = p.parcel_number "
    "WHERE p.parcel_number = ANY(:parcel_numbers) AND coalesce(p.is_vacant, false) = true"
)

_UPDATE_SQL = text(
    "UPDATE parcel AS p SET vacancy_confidence = v.conf "
    "FROM unnest(cast(:pns AS text[]), cast(:confs AS double precision[])) AS v(pn, conf) "
    "WHERE p.parcel_number = v.pn"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _signals(row: Row[Any]) -> VacancySignals:
    return VacancySignals(
        is_vacant=bool(row.is_vacant),
        vacancy_violations=row.vacancy_violations,
        demolitions=row.demolitions,
        recent_permits=row.recent_permits,
        improvement_value=_as_float(row.improvement_value),
        land_value=_as_float(row.land_value),
    )


async def recompute_vacancy_confidence(
    session: AsyncSession, parcel_numbers: Sequence[str]
) -> int:
    if not parcel_numbers:
        return 0
    rows = (
        await session.execute(_BULK_SIGNALS_SQL, {"parcel_numbers": list(parcel_numbers)})
    ).all()
    if not rows:
        return 0
    pns: list[str] = []
    confs: list[float] = []
    for row in rows:
        confidence = vacancy_confidence(_signals(row))
        if confidence is None:
            continue
        pns.append(row.parcel_number)
        confs.append(confidence)
    if not pns:
        return 0
    await session.execute(_UPDATE_SQL, {"pns": pns, "confs": confs})
    return len(pns)
