import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.tools.parcel_tools import (
    GetParcelInput,
    SearchAreaInput,
    get_parcel,
    search_area_tool,
)
from lotscope.agent.tools.registry import REGISTRY, ToolContext

pytestmark = pytest.mark.integration


async def _parcel(session: AsyncSession, parcel: str, address: str) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, base_zoning_code, "
            "is_vacant, lot_area_sqft, geom_local) VALUES (:p, 'phl', :a, 'RSA-5', true, 900, "
            "ST_SetSRID(ST_MakePoint(2690000, 240000), 2272))"
        ),
        {"p": parcel, "a": address},
    )
    await session.flush()


def test_both_tools_are_registered_with_schemas_written_for_the_model() -> None:
    names = REGISTRY.names()

    assert "get_parcel" in names
    assert "search_area" in names
    schemas = {schema["name"]: schema for schema in REGISTRY.schemas()}
    parcel = schemas["get_parcel"]["description"]
    assert "parcel number or street address" in parcel
    assert "computed when you ask" in parcel
    area = schemas["search_area"]["description"]
    assert "buy box" in area


async def test_get_parcel_resolves_an_address(db_session: AsyncSession) -> None:
    await _parcel(db_session, "phl:agent1", "2138 N FAIRHILL ST")

    result = await get_parcel(
        db_session, ToolContext(user_id=1), GetParcelInput(address="2138 N Fairhill St")
    )

    assert result.data["parcel_number"] == "phl:agent1"
    assert any(source.name == "opa_properties_public" for source in result.sources)
    assert any("Water" in item for item in result.unverified)


async def test_get_parcel_resolves_a_parcel_number(db_session: AsyncSession) -> None:
    await _parcel(db_session, "phl:agent2", "1 SOMEWHERE ST")

    result = await get_parcel(
        db_session, ToolContext(user_id=1), GetParcelInput(parcel_number="phl:agent2")
    )

    assert result.data["parcel_number"] == "phl:agent2"


async def test_an_unknown_parcel_comes_back_unverified_not_empty_handed(
    db_session: AsyncSession,
) -> None:
    result = await get_parcel(
        db_session, ToolContext(user_id=1), GetParcelInput(address="404 Nowhere St")
    )

    assert result.data == {}
    assert "No Philadelphia parcel matches" in result.unverified[0]


async def test_get_parcel_with_no_input_says_so(db_session: AsyncSession) -> None:
    result = await get_parcel(db_session, ToolContext(user_id=1), GetParcelInput())

    assert result.unverified == [
        "No parcel number or address was given, so nothing could be looked up."
    ]


async def test_search_area_inherits_the_lot_floor_from_the_buy_box(
    db_session: AsyncSession,
) -> None:
    context = ToolContext(user_id=1, buy_box={"min_lot_sqft": 640})

    result = await search_area_tool(
        db_session,
        context,
        SearchAreaInput(center_lat=39.99, center_lng=-75.14, radius_m=300),
    )

    applied = result.data["filters_applied"]
    assert applied["min_lot_sqft"] == 640
    assert applied["min_lot_sqft_came_from_buy_box"] is True


async def test_an_explicit_floor_beats_the_buy_box(db_session: AsyncSession) -> None:
    context = ToolContext(user_id=1, buy_box={"min_lot_sqft": 640})

    result = await search_area_tool(
        db_session,
        context,
        SearchAreaInput(center_lat=39.99, center_lng=-75.14, radius_m=300, min_lot_sqft=2000),
    )

    applied = result.data["filters_applied"]
    assert applied["min_lot_sqft"] == 2000
    assert applied["min_lot_sqft_came_from_buy_box"] is False


async def test_a_search_with_no_buy_box_says_nothing_was_screened(
    db_session: AsyncSession,
) -> None:
    result = await search_area_tool(
        db_session,
        ToolContext(user_id=1),
        SearchAreaInput(center_lat=39.99, center_lng=-75.14, radius_m=300),
    )

    assert any("no saved buy box" in item for item in result.unverified)


async def test_a_search_with_no_area_is_refused_clearly(db_session: AsyncSession) -> None:
    result = await search_area_tool(db_session, ToolContext(user_id=1), SearchAreaInput())

    assert result.data == {}
    assert "supply either a centre with a radius, or a polygon ring" in result.unverified[0]


def test_importing_the_api_registers_the_tools() -> None:
    from lotscope.api.app import create_app

    create_app()

    assert REGISTRY.names() == ["get_parcel", "search_area"]
    assert len(REGISTRY.schemas()) == 2
