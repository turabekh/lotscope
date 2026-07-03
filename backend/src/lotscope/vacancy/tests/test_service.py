from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.vacancy.scoring import LOW_CONFIDENCE_THRESHOLD, VPI_BASELINE
from lotscope.vacancy.service import recompute_vacancy_confidence

pytestmark = pytest.mark.integration


async def _add_parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    is_vacant: bool | None,
    improvement_value: float | None = None,
    land_value: float | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, is_vacant, improvement_value, land_value) "
            "VALUES (:pn, :vacant, :imp, :land)"
        ),
        {"pn": parcel_number, "vacant": is_vacant, "imp": improvement_value, "land": land_value},
    )


async def _add_event(
    session: AsyncSession,
    parcel_number: str,
    *,
    event_type: str,
    description: str | None = None,
    event_date: date | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO li_event "
            "(parcel_number, external_id, event_type, description, event_date) "
            "VALUES (:pn, :ext, :etype, :desc, :edate)"
        ),
        {
            "pn": parcel_number,
            "ext": f"{event_type}-{parcel_number}-{description or event_date}",
            "etype": event_type,
            "desc": description,
            "edate": event_date,
        },
    )


async def _confidence(session: AsyncSession, parcel_number: str) -> float | None:
    value = await session.scalar(
        text("SELECT vacancy_confidence FROM parcel WHERE parcel_number = :pn"),
        {"pn": parcel_number},
    )
    return float(value) if value is not None else None


async def test_corroborated_vacant_lot_scores_above_baseline(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", is_vacant=True)
    await _add_event(db_session, "000000001", event_type="violation", description="VACANT LOT")
    await _add_event(db_session, "000000001", event_type="demolition")
    await db_session.flush()

    updated = await recompute_vacancy_confidence(db_session, ["000000001"])
    assert updated == 1
    confidence = await _confidence(db_session, "000000001")
    assert confidence is not None
    assert confidence > VPI_BASELINE


async def test_contradicted_vacant_lot_scores_low(db_session: AsyncSession) -> None:
    await _add_parcel(
        db_session, "000000002", is_vacant=True, improvement_value=200000, land_value=40000
    )
    await _add_event(
        db_session, "000000002", event_type="permit", description="NEW", event_date=date(2025, 1, 1)
    )
    await db_session.flush()

    await recompute_vacancy_confidence(db_session, ["000000002"])
    confidence = await _confidence(db_session, "000000002")
    assert confidence is not None
    assert confidence < LOW_CONFIDENCE_THRESHOLD


async def test_non_vacant_parcel_is_left_untouched(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000003", is_vacant=False)
    await db_session.flush()

    updated = await recompute_vacancy_confidence(db_session, ["000000003"])
    assert updated == 0
    assert await _confidence(db_session, "000000003") is None
