from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ops.gates import GRADUATION, PARITY, seed_market_gates
from lotscope.ops.models import MarketGateItem
from lotscope.ops.service import gate_board

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


async def test_seed_transcribes_gate_docs_and_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_market_gates(db_session)
    await db_session.flush()
    second = await seed_market_gates(db_session)
    await db_session.flush()
    assert first == second

    hbg_graduation = await db_session.scalar(
        select(func.count())
        .select_from(MarketGateItem)
        .where(
            MarketGateItem.market_code == "hbg",
            MarketGateItem.gate_type == GRADUATION,
        )
    )
    assert hbg_graduation == 8


async def test_graduation_rollup_matches_doc_headline_count(db_session: AsyncSession) -> None:
    await seed_market_gates(db_session)
    await db_session.flush()

    board = await gate_board(db_session, _NOW)
    hbg = next(m for m in board.markets if m.market_code == "hbg")
    graduation = next(g for g in hbg.gates if g.gate_type == GRADUATION)

    assert graduation.total == 8
    assert graduation.satisfied == 4

    scoped = next(i for i in graduation.items if i.qualifier == "repository only")
    assert scoped.status == "met"
    assert scoped.satisfied is False


async def test_parity_gates_pass_including_honest_degradation(db_session: AsyncSession) -> None:
    await seed_market_gates(db_session)
    await db_session.flush()

    board = await gate_board(db_session, _NOW)
    for code in ("hbg", "pgh"):
        market = next(m for m in board.markets if m.market_code == code)
        parity = next(g for g in market.gates if g.gate_type == PARITY)
        assert parity.total == 6
        assert parity.satisfied == 6
        comp = next(i for i in parity.items if i.status == "honest_degradation")
        assert comp.satisfied is True
        assert comp.threshold is not None


async def test_live_market_has_no_gate_board_entry(db_session: AsyncSession) -> None:
    await seed_market_gates(db_session)
    await db_session.flush()

    board = await gate_board(db_session, _NOW)
    assert all(m.market_code != "phl" for m in board.markets)


async def test_wlm_parity_gate_reports_measured_coverage_but_is_not_graduated(
    db_session: AsyncSession,
) -> None:
    await seed_market_gates(db_session)
    await db_session.flush()

    board = await gate_board(db_session, _NOW)
    wlm = next(m for m in board.markets if m.market_code == "wlm")
    parity = next(g for g in wlm.gates if g.gate_type == PARITY)

    assert parity.total == 7
    assert parity.satisfied < parity.total
    distress = next(i for i in parity.items if i.status == "honest_degradation")
    assert "reduced" in distress.title.lower()
    assert distress.satisfied is True

    blocked = [i for i in parity.items if i.status == "blocked"]
    assert [i.title for i in blocked] == ["25-parcel golden packet + reviewer sign-off"]
    assert all(i.owner == "operator" for i in blocked)


async def test_wlm_parity_coverage_rows_carry_a_measured_value_not_a_blocker(
    db_session: AsyncSession,
) -> None:
    await seed_market_gates(db_session)
    await db_session.flush()

    board = await gate_board(db_session, _NOW)
    wlm = next(m for m in board.markets if m.market_code == "wlm")
    parity = next(g for g in wlm.gates if g.gate_type == PARITY)

    coverage = [i for i in parity.items if i.status == "pass"]
    assert len(coverage) == 5
    assert all(i.measured for i in coverage)
    assert not any("blocker" in (i.measured or "").lower() for i in coverage)
