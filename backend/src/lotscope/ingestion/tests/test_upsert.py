import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

pytestmark = pytest.mark.integration


async def test_upsert_is_idempotent_on_conflict(db_session: AsyncSession) -> None:
    inserted = await upsert(
        db_session,
        Parcel,
        [{"parcel_number": "100", "owner": "Owner A"}],
        index_elements=["parcel_number"],
    )
    await db_session.flush()
    assert inserted == 1

    await upsert(
        db_session,
        Parcel,
        [{"parcel_number": "100", "owner": "Owner B"}],
        index_elements=["parcel_number"],
    )
    await db_session.flush()

    owner = await db_session.scalar(select(Parcel.owner).where(Parcel.parcel_number == "100"))
    count = await db_session.scalar(select(func.count()).select_from(Parcel))
    assert owner == "Owner B"
    assert count == 1


async def test_upsert_only_updates_provided_columns(db_session: AsyncSession) -> None:
    await upsert(
        db_session,
        Parcel,
        [{"parcel_number": "200", "owner": "Keep", "zip_code": "19104"}],
        index_elements=["parcel_number"],
    )
    await db_session.flush()
    await upsert(
        db_session,
        Parcel,
        [{"parcel_number": "200", "zip_code": "19147"}],
        index_elements=["parcel_number"],
    )
    await db_session.flush()

    row = (
        await db_session.execute(
            select(Parcel.owner, Parcel.zip_code).where(Parcel.parcel_number == "200")
        )
    ).one()
    assert row.owner == "Keep"
    assert row.zip_code == "19147"


async def test_record_freshness_tracks_success(db_session: AsyncSession) -> None:
    await record_freshness(db_session, "opa", status="running")
    await db_session.flush()
    await record_freshness(db_session, "opa", status="success", success=True, row_count=42)
    await db_session.flush()

    record = await db_session.get(DatasetFreshness, ("phl", "opa"))
    assert record is not None
    assert record.status == "success"
    assert record.row_count == 42
    assert record.last_success_at is not None
