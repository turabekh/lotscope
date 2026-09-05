import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.tools.action_tools import (
    AddToPipelineInput,
    CreateAlertInput,
    DraftLetterInput,
    ExportCsvInput,
    NoInput,
    ScreenParcelsInput,
    ScreenSaleInput,
    UpdateDealInput,
    WatchInput,
    add_to_pipeline_tool,
    create_alert_tool,
    draft_letter_tool,
    export_csv_tool,
    list_pipeline_tool,
    screen_parcels_tool,
    screen_sale_tool,
    unwatch_tool,
    update_deal_tool,
    watch_tool,
)
from lotscope.agent.tools.registry import REGISTRY, ToolContext

pytestmark = pytest.mark.integration

RUN_ID_MARKER = 4242


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'user', true)"
        ),
        {"e": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _run_for(session: AsyncSession, user_id: int) -> int:
    await session.execute(
        text("INSERT INTO agent_conversation (user_id) VALUES (:u)"),
        {"u": user_id},
    )
    await session.flush()
    conversation_id = int(await session.scalar(text("SELECT max(id) FROM agent_conversation")))
    await session.execute(
        text(
            "INSERT INTO agent_run (conversation_id, user_id, status, model, question) "
            "VALUES (:c, :u, 'running', 'fake', 'q')"
        ),
        {"c": conversation_id, "u": user_id},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT max(id) FROM agent_run")))


async def _parcel(session: AsyncSession, parcel: str, address: str) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, mailing_address, "
            "base_zoning_code, is_vacant, lot_area_sqft, market_value, geom_local, geom_4326) "
            "VALUES (:p, 'phl', :a, 'ACME LLC', '1 MAIN ST PHILADELPHIA PA 19100', 'RSA-5', "
            "true, 900, 40000, ST_SetSRID(ST_MakePoint(2690000, 240000), 2272), "
            "ST_SetSRID(ST_MakePoint(-75.14, 39.99), 4326))"
        ),
        {"p": parcel, "a": address},
    )
    await session.flush()


async def _context(session: AsyncSession, email: str) -> tuple[ToolContext, int]:
    user_id = await _user(session, email)
    run_id = await _run_for(session, user_id)
    return ToolContext(user_id=user_id, agent_run_id=run_id), run_id


def test_every_action_tool_is_registered_with_a_description_for_the_model() -> None:
    schemas = {schema["name"]: schema for schema in REGISTRY.schemas()}
    for name in (
        "compute_deal",
        "run_sensitivity",
        "screen_sale",
        "screen_parcels",
        "add_to_pipeline",
        "update_deal",
        "list_pipeline",
        "watch",
        "unwatch",
        "draft_loi",
        "draft_letter",
        "create_alert",
        "export_csv",
    ):
        assert name in schemas, name
        assert len(schemas[name]["description"]) > 60, name


async def test_adding_to_the_pipeline_records_the_run_that_did_it(
    db_session: AsyncSession,
) -> None:
    context, run_id = await _context(db_session, "pipeline-run@example.com")
    await _parcel(db_session, "phl:act1", "1 ACTION ST")

    result = await add_to_pipeline_tool(
        db_session, context, AddToPipelineInput(parcel="1 Action St", stage="lead")
    )

    assert result.data["parcel_number"] == "phl:act1"
    assert result.data["added_by_run"] == run_id
    stored = await db_session.scalar(
        text("SELECT agent_run_id FROM deal WHERE parcel_number = :p"), {"p": "phl:act1"}
    )
    assert stored == run_id


async def test_adding_the_same_lot_twice_does_not_duplicate(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "dupe@example.com")
    await _parcel(db_session, "phl:act2", "2 ACTION ST")

    await add_to_pipeline_tool(db_session, context, AddToPipelineInput(parcel="phl:act2"))
    await add_to_pipeline_tool(db_session, context, AddToPipelineInput(parcel="phl:act2"))

    count = await db_session.scalar(
        text("SELECT count(*) FROM deal WHERE parcel_number = :p"), {"p": "phl:act2"}
    )
    assert count == 1


async def test_an_unknown_parcel_is_reported_not_added(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "missing@example.com")

    result = await add_to_pipeline_tool(
        db_session, context, AddToPipelineInput(parcel="404 Nowhere St")
    )

    assert result.data == {}
    assert "No Philadelphia parcel matches" in result.unverified[0]


async def test_the_pipeline_lists_what_was_added(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "list@example.com")
    await _parcel(db_session, "phl:act3", "3 ACTION ST")
    await add_to_pipeline_tool(db_session, context, AddToPipelineInput(parcel="phl:act3"))

    result = await list_pipeline_tool(db_session, context, NoInput())

    assert result.data["count"] == 1
    assert result.data["deals"][0]["parcel_number"] == "phl:act3"


async def test_an_empty_pipeline_says_so_rather_than_looking_broken(
    db_session: AsyncSession,
) -> None:
    context, _ = await _context(db_session, "emptypipe@example.com")

    result = await list_pipeline_tool(db_session, context, NoInput())

    assert result.data["count"] == 0
    assert result.unverified == ["This buyer's pipeline is empty."]


async def test_updating_a_deal_that_is_not_theirs_is_refused(db_session: AsyncSession) -> None:
    mine, _ = await _context(db_session, "mine@example.com")
    theirs, _ = await _context(db_session, "theirs@example.com")
    await _parcel(db_session, "phl:act4", "4 ACTION ST")
    added = await add_to_pipeline_tool(db_session, mine, AddToPipelineInput(parcel="phl:act4"))

    result = await update_deal_tool(
        db_session, theirs, UpdateDealInput(deal_id=added.data["deal_id"], stage="offer")
    )

    assert result.data == {}
    assert "not in this buyer's pipeline" in result.unverified[0]


async def test_watching_records_the_run_and_unwatching_reverses_it(
    db_session: AsyncSession,
) -> None:
    context, run_id = await _context(db_session, "watch@example.com")
    await _parcel(db_session, "phl:act5", "5 ACTION ST")

    watched = await watch_tool(db_session, context, WatchInput(parcel="phl:act5"))
    stored = await db_session.scalar(
        text("SELECT agent_run_id FROM saved_parcel WHERE parcel_number = :p"), {"p": "phl:act5"}
    )
    removed = await unwatch_tool(db_session, context, WatchInput(parcel="phl:act5"))

    assert watched.data["watching"] is True
    assert stored == run_id
    assert removed.data["watching"] is False
    assert removed.data["was_watching"] is True


async def test_unwatching_something_never_watched_says_so(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "neverwatched@example.com")
    await _parcel(db_session, "phl:act6", "6 ACTION ST")

    result = await unwatch_tool(db_session, context, WatchInput(parcel="phl:act6"))

    assert result.data["was_watching"] is False
    assert "was not on the saved list" in result.unverified[0]


async def test_an_alert_is_persisted_with_the_run_and_not_duplicated(
    db_session: AsyncSession,
) -> None:
    context, run_id = await _context(db_session, "alert@example.com")
    await _parcel(db_session, "phl:act7", "7 ACTION ST")

    first = await create_alert_tool(
        db_session, context, CreateAlertInput(kind="sale_status", scope="parcel", parcel="phl:act7")
    )
    second = await create_alert_tool(
        db_session, context, CreateAlertInput(kind="sale_status", scope="parcel", parcel="phl:act7")
    )

    assert first.data["created_by_run"] == run_id
    assert second.data["already_existed"] is True
    assert second.data["alert_id"] == first.data["alert_id"]
    count = await db_session.scalar(text("SELECT count(*) FROM agent_alert"))
    assert count == 1


async def test_a_neighbours_alert_needs_parcels_they_actually_own(
    db_session: AsyncSession,
) -> None:
    context, _ = await _context(db_session, "noowned@example.com")

    result = await create_alert_tool(
        db_session, context, CreateAlertInput(kind="neighbor_deed", scope="owned_neighbors")
    )

    assert result.data == {}
    assert "recorded no parcels of their own" in result.unverified[0]


async def test_screening_a_sale_date_with_no_listing_says_so(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "nosale@example.com")

    result = await screen_sale_tool(db_session, context, ScreenSaleInput(sale_date="2099-01-01"))

    assert result.data == {}
    assert "No sheriff-sale listing" in result.unverified[0]


async def test_a_malformed_sale_date_is_refused_clearly(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "baddate@example.com")

    result = await screen_sale_tool(db_session, context, ScreenSaleInput(sale_date="next Tuesday"))

    assert "is not a date in YYYY-MM-DD form" in result.unverified[0]


async def test_screening_parcels_grades_and_sorts_bids_first(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "screen@example.com")
    await _parcel(db_session, "phl:act8", "8 ACTION ST")
    await _parcel(db_session, "phl:act9", "9 ACTION ST")

    result = await screen_parcels_tool(
        db_session, context, ScreenParcelsInput(parcel_numbers=["phl:act8", "phl:act9"])
    )

    assert result.data["screened"] == 2
    verdicts = [entry["verdict"] for entry in result.data["results"]]
    assert verdicts == sorted(verdicts, key=lambda v: {"BID": 0, "LOOK": 1, "PASS": 2}[v])


async def test_screening_with_neither_parcels_nor_an_area_is_refused(
    db_session: AsyncSession,
) -> None:
    context, _ = await _context(db_session, "noarea@example.com")

    result = await screen_parcels_tool(db_session, context, ScreenParcelsInput())

    assert "Give either parcel numbers or a centre point" in result.unverified[0]


async def test_a_drafted_letter_is_written_but_never_sent(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "letter@example.com")
    await _parcel(db_session, "phl:act10", "10 ACTION ST")

    result = await draft_letter_tool(
        db_session, context, DraftLetterInput(parcel="phl:act10", body="Hello.")
    )

    from pathlib import Path

    assert result.data["sent"] is False
    assert Path(result.data["pdf_path"]).exists()
    assert any("was not sent" in item for item in result.unverified)


async def test_a_letter_with_no_mailing_address_is_refused(db_session: AsyncSession) -> None:
    context, _ = await _context(db_session, "nomail@example.com")
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, is_vacant) "
            "VALUES ('phl:act11', 'phl', '11 ACTION ST', 'NOBODY LLC', true)"
        )
    )
    await db_session.flush()

    result = await draft_letter_tool(db_session, context, DraftLetterInput(parcel="phl:act11"))

    assert result.data == {}
    assert "No mailing address" in result.unverified[0]


async def test_an_export_writes_a_csv_and_names_what_was_missing(
    db_session: AsyncSession,
) -> None:
    context, _ = await _context(db_session, "export@example.com")
    await _parcel(db_session, "phl:act12", "12 ACTION ST")

    result = await export_csv_tool(
        db_session, context, ExportCsvInput(parcel_numbers=["phl:act12", "phl:not-real"])
    )

    from pathlib import Path

    path = Path(result.data["path"])
    assert path.exists()
    assert result.data["rows"] == 1
    assert "1 of the parcels asked for are not in the parcel table." in result.unverified
    body = path.read_text()
    assert "phl:act12" in body
    assert "12 ACTION ST" in body
