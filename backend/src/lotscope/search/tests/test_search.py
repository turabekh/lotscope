import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_session
from lotscope.search.service import _like_escape, _padded_account, search_parcels


def _member() -> User:
    return User(
        id=1,
        email="member@example.com",
        hashed_password="x",
        full_name=None,
        role="user",
        tier="free",
    )


def test_padded_account_pads_short_digit_runs() -> None:
    assert _padded_account("12345") == "000012345"
    assert _padded_account("000012345") == "000012345"
    assert _padded_account("") == ""
    assert _padded_account("main st") == ""
    assert _padded_account("1234567890") == ""


def test_like_escape_neutralizes_wildcards() -> None:
    assert _like_escape("50%") == "50\\%"
    assert _like_escape("a_b") == "a\\_b"


async def _seed(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, owner) VALUES "
            "('000012345', '123 MAIN ST', 'JANE SMITH'), "
            "('000099999', '456 OAK AVE', 'JOHN DOE')"
        )
    )
    await session.flush()


@pytest.mark.integration
async def test_search_matches_address_owner_and_number(db_session: AsyncSession) -> None:
    await _seed(db_session)

    by_address = await search_parcels(db_session, "main")
    assert any(result.parcel_number == "000012345" for result in by_address)

    by_owner = await search_parcels(db_session, "smith")
    assert by_owner[0].parcel_number == "000012345"

    by_number = await search_parcels(db_session, "12345")
    assert any(result.parcel_number == "000012345" for result in by_number)

    assert await search_parcels(db_session, "   ") == []


@pytest.mark.integration
async def test_search_endpoint_returns_results(db_session: AsyncSession) -> None:
    await _seed(db_session)

    app = create_app()

    async def _override_session() -> object:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_current_user] = _member
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/search", params={"q": "main", "market": "philadelphia"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "main"
    assert body["market"] == "philadelphia"
    assert any(item["parcel_number"] == "000012345" for item in body["results"])

