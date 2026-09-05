"""The eval's stale-state helper must put back exactly what it changed.

These tasks edit the real local database to make LotScope's copy wrong on purpose. If the
restore is not exact, running the eval quietly corrupts the data every other test reads.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.evals import stale

pytestmark = pytest.mark.integration


async def _parcel(session: AsyncSession, parcel: str) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, land_use) "
            "VALUES (:p, 'phl', '9 STALE ST', 'REAL OWNER LLC', 'VACANT LAND')"
        ),
        {"p": parcel},
    )
    await session.commit()


async def test_an_edit_is_applied_and_then_restored_exactly(db_session: AsyncSession) -> None:
    await _parcel(db_session, "phl:stale1")
    edits = stale.parse(
        [{"table": "parcel", "where": {"parcel_number": "phl:stale1"}, "set": {"owner": "WRONG"}}]
    )

    planted = await stale.apply(db_session, edits)
    assert (
        await db_session.scalar(text("SELECT owner FROM parcel WHERE parcel_number = 'phl:stale1'"))
        == "WRONG"
    )

    await stale.undo(db_session, planted)
    assert (
        await db_session.scalar(text("SELECT owner FROM parcel WHERE parcel_number = 'phl:stale1'"))
        == "REAL OWNER LLC"
    )


async def test_an_edit_that_matches_nothing_fails_loudly(db_session: AsyncSession) -> None:
    edits = stale.parse(
        [{"table": "parcel", "where": {"parcel_number": "phl:nope"}, "set": {"owner": "WRONG"}}]
    )
    with pytest.raises(ValueError, match="would be a no-op"):
        await stale.apply(db_session, edits)


def test_a_table_the_eval_may_not_touch_is_refused() -> None:
    with pytest.raises(ValueError, match="not a table the eval may edit"):
        stale.parse([{"table": "app_user", "where": {"id": 1}, "set": {"email": "x"}}])


def test_a_column_outside_the_whitelist_is_refused() -> None:
    with pytest.raises(ValueError, match="not an editable column"):
        stale.parse(
            [{"table": "parcel", "where": {"parcel_number": "p"}, "set": {"geom_4326": None}}]
        )


def test_every_task_with_a_stale_block_parses() -> None:
    from lotscope.agent.evals.runner import load_tasks

    edited = [task for task in load_tasks() if task.get("stale")]
    assert len(edited) == 5
    for task in edited:
        assert stale.parse(task["stale"])


async def test_a_correction_the_planted_staleness_caused_is_withdrawn(
    db_session: AsyncSession,
) -> None:
    """A correction filed against an invented disagreement must not outlive the task."""
    await _parcel(db_session, "phl:stale2")
    user_id = int(
        await db_session.scalar(
            text(
                "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
                "VALUES ('stale-corr@example.com', 'x', 'user', 'user', true) RETURNING id"
            )
        )
    )
    edits = stale.parse(
        [{"table": "parcel", "where": {"parcel_number": "phl:stale2"}, "set": {"owner": "WRONG"}}]
    )
    planted = await stale.apply(db_session, edits)

    # Two corrections: one the planted staleness would provoke, one about another parcel.
    for parcel in ("phl:stale2", "phl:stale1-other"):
        await db_session.execute(
            text(
                "INSERT INTO parcel_correction (parcel_number, market_code, reported_by, "
                "section, field_name, description, status) VALUES (:p, 'phl', :u, 'ownership', "
                "'owner', 'live disagrees with stored', 'open')"
            ),
            {"p": parcel, "u": user_id},
        )
    await db_session.commit()

    await stale.undo(db_session, planted)

    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM parcel_correction WHERE parcel_number = 'phl:stale2'")
        )
        == 0
    )
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM parcel_correction WHERE parcel_number = 'phl:stale1-other'")
        )
        == 1
    )
