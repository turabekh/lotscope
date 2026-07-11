from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ops.service import fleet_overview, market_health
from lotscope.verdict.composition import VERDICT_VERSION

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


async def _seed_phl(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO dataset_freshness "
            "(market_code, dataset, status, last_attempt_at, last_success_at, row_count) VALUES "
            "('phl', 'opa_properties_public', 'success', now(), now(), 100), "
            "('phl', 'rtt_summary', 'failed', now(), now() - interval '1 day', 50)"
        )
    )
    await session.execute(
        text(
            "INSERT INTO market_stats "
            "(market_code, parcel_count, geometry_pct, verdict_pct, vacant_count, "
            "vacant_with_comp_pct, computed_at) VALUES "
            "('phl', 2, 100.0, 50.0, 1, 100.0, now())"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, is_vacant) VALUES "
            "('phl:o-1', 'phl', true), ('phl:o-2', 'phl', false)"
        )
    )
    await session.execute(
        text("INSERT INTO parcel_verdict (parcel_number, verdict_version) VALUES ('phl:o-1', :vv)"),
        {"vv": VERDICT_VERSION},
    )
    await session.flush()


async def test_fleet_overview_rolls_up_worst_dataset_status(db_session: AsyncSession) -> None:
    await _seed_phl(db_session)

    overview = await fleet_overview(db_session, _NOW, "abc1234")

    assert overview.git_sha == "abc1234"
    phl = next(m for m in overview.markets if m.market_code == "phl")
    assert phl.health.status == "red"
    assert phl.health.red == 1
    assert phl.health.green == 1
    assert phl.coverage.parcel_count == 2
    assert phl.coverage.geometry_pct == 100.0
    assert phl.last_ingest_at is not None


async def test_market_health_reports_datasets_and_verdict_spread(
    db_session: AsyncSession,
) -> None:
    await _seed_phl(db_session)

    detail = await market_health(db_session, "phl", _NOW)
    assert detail is not None
    datasets = {d.dataset: d for d in detail.datasets}
    assert datasets["rtt_summary"].freshness == "red"
    assert datasets["opa_properties_public"].freshness == "green"

    versions = {v.verdict_version: v.count for v in detail.verdict_versions}
    assert versions.get(VERDICT_VERSION) == 1
    assert versions.get(None) == 1


async def test_market_health_surfaces_capability_gaps(db_session: AsyncSession) -> None:
    detail = await market_health(db_session, "hbg", _NOW)
    assert detail is not None
    categories = {c.category for c in detail.capabilities}
    assert "li" in categories
    li = next(c for c in detail.capabilities if c.category == "li")
    assert li.state == "no_data_source"
    assert li.detail


async def test_market_health_unknown_market_is_none(db_session: AsyncSession) -> None:
    assert await market_health(db_session, "nope", _NOW) is None
