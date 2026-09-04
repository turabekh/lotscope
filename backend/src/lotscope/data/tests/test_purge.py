import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.data.purge import (
    EXPLICIT_LISTED,
    EXPLICIT_PARCEL_KEYED_TABLES,
    FK_REACHED,
    build_deletion_graph,
    count_targets,
    delete_targets,
    load_full_metadata,
)


def _toy_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "parcel",
        metadata,
        Column("parcel_number", String, primary_key=True),
        Column("market_code", String),
    )
    Table(
        "deal",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parcel_number", String, ForeignKey("parcel.parcel_number")),
    )
    Table(
        "deal_activity",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("deal_id", Integer, ForeignKey("deal.id")),
    )
    Table("unrelated", metadata, Column("id", Integer, primary_key=True))
    return metadata


def _by_key(targets: list) -> dict:
    return {t.key: t for t in targets}


def test_the_graph_reaches_a_grandchild_through_its_parent() -> None:
    targets = _by_key(build_deletion_graph(_toy_metadata()))

    assert "deal_activity" in targets, "a child of a child must be reached"
    predicate = targets["deal_activity"].predicate
    assert "deal_id IN (SELECT id FROM deal" in predicate
    assert "parcel_number IN (SELECT parcel_number FROM parcel" in predicate
    assert "market_code <> 'phl'" in predicate


def test_a_table_with_no_path_to_parcel_is_left_alone() -> None:
    assert "unrelated" not in _by_key(build_deletion_graph(_toy_metadata()))


def test_parcel_is_deleted_last_and_children_before_parents() -> None:
    order = [t.key for t in build_deletion_graph(_toy_metadata())]

    assert order[-1] == "parcel"
    assert order.index("deal_activity") < order.index("deal") < order.index("parcel")


def test_the_walk_starts_from_the_market_predicate() -> None:
    targets = _by_key(build_deletion_graph(_toy_metadata(), market_code="phl"))
    assert targets["parcel"].predicate == "market_code <> 'phl'"


def test_explicit_tables_are_labelled_apart_from_foreign_key_reached_ones() -> None:
    targets = _by_key(build_deletion_graph(load_full_metadata()))

    assert targets["parcel_verdict"].reason == FK_REACHED
    assert targets["parcel_overlay"].reason == EXPLICIT_LISTED
    assert targets["parcel_overlay"].note


def test_every_explicitly_listed_table_carries_a_reason_for_being_listed() -> None:
    for entry in EXPLICIT_PARCEL_KEYED_TABLES:
        assert entry.note, f"{entry.key} must document why it needs listing by hand"


def test_the_real_graph_covers_every_table_that_keys_on_a_parcel() -> None:
    metadata = load_full_metadata()
    covered = {t.key for t in build_deletion_graph(metadata)}
    keyed = {t.key for t in metadata.sorted_tables if "parcel_number" in t.c}

    assert keyed - covered == set(), (
        "a table keyed on parcel_number is not in the deletion graph; "
        "add it to EXPLICIT_PARCEL_KEYED_TABLES"
    )


@pytest.mark.integration
async def test_counting_and_deleting_agree_on_the_same_predicate(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address) VALUES "
            "('zzz:1', 'zzz', '1 GONE ST'), ('zzz:2', 'zzz', '2 GONE ST'), "
            "('000000801', 'phl', '3 KEPT ST')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_verdict (parcel_number, verdict_version) VALUES "
            "('zzz:1', 'v1'), ('000000801', 'v1')"
        )
    )
    await db_session.flush()

    targets = [
        t
        for t in build_deletion_graph(load_full_metadata())
        if t.key in {"parcel", "parcel_verdict"}
    ]
    before = {t.key: c for t, c in await count_targets(db_session, targets)}
    assert before["parcel"] == 2
    assert before["parcel_verdict"] == 1

    deleted = {t.key: c for t, c in await delete_targets(db_session, targets)}
    await db_session.flush()

    assert deleted == before, "the delete must remove exactly what the dry run counted"
    kept = await db_session.scalar(
        text("SELECT count(*) FROM parcel WHERE parcel_number = '000000801'")
    )
    assert kept == 1, "a Philadelphia parcel must survive the purge"


@pytest.mark.integration
async def test_an_absent_table_is_reported_rather_than_raising(db_session: AsyncSession) -> None:
    from lotscope.data.purge import PurgeTarget

    target = PurgeTarget(key="no_such_table", reason=EXPLICIT_LISTED, predicate="true")
    assert await count_targets(db_session, [target]) == [(target, None)]
