import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.retention import sweep_retention

_SEED_PARCEL = text("INSERT INTO parcel (parcel_number) VALUES ('000000001')")
_SEED_RUN = text("INSERT INTO ingest_run (dataset) VALUES ('rtt_summary') RETURNING id")
_SEED_RAW = text(
    "INSERT INTO raw.raw_record (ingest_run_id, dataset, natural_key, payload, fetched_at) VALUES "
    "(:rid, 'rtt_summary', 'old', '{}'::jsonb, now() - interval '200 days'), "
    "(:rid, 'rtt_summary', 'fresh', '{}'::jsonb, now())"
)
_SEED_EVENTS = text(
    "INSERT INTO parcel_event "
    "(parcel_number, dataset, code, severity, detected_at, ingest_run_id) VALUES "
    "('000000001', 'rtt', 'new_deed', 'low', now() - interval '20 months', :rid), "
    "('000000001', 'rtt', 'new_deed', 'low', now(), :rid)"
)


@pytest.mark.integration
async def test_sweep_deletes_expired_and_keeps_fresh(db_session: AsyncSession) -> None:
    await db_session.execute(_SEED_PARCEL)
    run_id = await db_session.scalar(_SEED_RUN)
    await db_session.execute(_SEED_RAW, {"rid": run_id})
    await db_session.execute(_SEED_EVENTS, {"rid": run_id})

    result = await sweep_retention(db_session, raw_retention_days=90, event_retention_months=18)

    assert result.raw_deleted == 1
    assert result.events_deleted == 1

    remaining_raw = await db_session.scalar(
        text("SELECT natural_key FROM raw.raw_record ORDER BY natural_key")
    )
    assert remaining_raw == "fresh"

    event_count = await db_session.scalar(text("SELECT count(*) FROM parcel_event"))
    assert event_count == 1


@pytest.mark.integration
async def test_sweep_is_noop_when_nothing_expired(db_session: AsyncSession) -> None:
    await db_session.execute(_SEED_PARCEL)
    run_id = await db_session.scalar(_SEED_RUN)
    await db_session.execute(_SEED_RAW, {"rid": run_id})
    await db_session.execute(_SEED_EVENTS, {"rid": run_id})

    result = await sweep_retention(db_session, raw_retention_days=3650, event_retention_months=600)

    assert result.raw_deleted == 0
    assert result.events_deleted == 0
