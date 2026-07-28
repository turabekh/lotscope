import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.verdict.models import ParcelVerdict
from lotscope.verdict.service import (
    compute_verdict,
    get_or_compute_current_verdict,
    get_verdict,
    recompute_verdicts,
)
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


async def _setup_parcel(session: AsyncSession) -> None:
    await seed_zoning_standards(session)
    await session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "market_value, base_zoning_code, geom_local) VALUES "
            "('000000001', 1600, 18, 90, 150000, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed) "
            "VALUES ('000000001', true, 20000, 4)"
        )
    )
    await session.flush()


async def test_compute_verdict_persists_composed_row(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)

    result = await compute_verdict(db_session, "000000001")
    await db_session.flush()

    assert result is not None
    assert result.verdict_version == VERDICT_VERSION
    assert result.can_build_by_right is True
    assert result.risk_score is not None
    assert result.risk_score > 0
    assert "RSA-5" in result.summary

    stored = await db_session.get(ParcelVerdict, "000000001")
    assert stored is not None
    assert stored.verdict_version == VERDICT_VERSION
    assert stored.summary == result.summary
    assert stored.computed_at is not None
    assert any(flag["code"] == "tax_delinquency" for flag in stored.risk_flags)


async def test_compute_verdict_is_idempotent(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)

    await compute_verdict(db_session, "000000001")
    await db_session.flush()
    await compute_verdict(db_session, "000000001")
    await db_session.flush()

    count = await db_session.scalar(select(func.count()).select_from(ParcelVerdict))
    assert count == 1


async def test_recompute_verdicts_batch(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000002')"))
    await db_session.flush()

    processed = await recompute_verdicts(db_session, ["000000001", "000000002", "999999999"])
    assert processed == 2


async def test_recompute_verdicts_skips_a_failing_parcel(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lotscope.verdict import service as verdict_service

    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number) VALUES ('000000001'), ('000000002'), ('000000003')"
        )
    )
    await db_session.flush()

    attempted: list[str] = []

    async def flaky(session: AsyncSession, parcel_number: str) -> object:
        attempted.append(parcel_number)
        if parcel_number == "000000002":
            await session.execute(text("SELECT 1 / 0"))  # poison the subtransaction
        return object()

    monkeypatch.setattr(verdict_service, "compute_verdict", flaky)

    processed = await verdict_service.recompute_verdicts(
        db_session, ["000000001", "000000002", "000000003"]
    )
    assert processed == 2  # the bad one is skipped, not fatal
    assert attempted == ["000000001", "000000002", "000000003"]  # all attempted
    assert await db_session.scalar(text("SELECT 1")) == 1  # session still usable


async def test_compute_verdict_returns_none_when_missing(db_session: AsyncSession) -> None:
    assert await compute_verdict(db_session, "999999999") is None


@pytest.mark.integration
async def test_field_trust_survives_the_cached_read_path(db_session: AsyncSession) -> None:
    await _setup_parcel(db_session)

    computed = await compute_verdict(db_session, "000000001")
    await db_session.flush()
    assert computed is not None
    assert computed.field_trust

    cached = await get_or_compute_current_verdict(db_session, "000000001")
    assert cached is not None
    assert cached.field_trust == computed.field_trust
    assert cached.field_trust["can_build_by_right"].status == "calculated"


@pytest.mark.integration
async def test_a_verdict_stored_before_the_contract_reads_as_no_states(
    db_session: AsyncSession,
) -> None:
    await _setup_parcel(db_session)
    await compute_verdict(db_session, "000000001")
    await db_session.flush()
    await db_session.execute(
        text("UPDATE parcel_verdict SET field_trust = NULL WHERE parcel_number = '000000001'")
    )
    await db_session.flush()
    db_session.expire_all()

    legacy = await get_verdict(db_session, "000000001")
    assert legacy is not None
    assert legacy.field_trust == {}
