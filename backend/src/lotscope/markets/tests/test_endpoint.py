import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import get_session


@pytest.mark.integration
async def test_markets_endpoint_lists_philadelphia(db_session: AsyncSession) -> None:
    app = create_app()

    async def _override_session() -> object:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/markets")

    assert response.status_code == 200
    body = response.json()
    phl = next(m for m in body if m["code"] == "phl")
    assert phl["url_slug"] == "philadelphia"
    assert len(phl["map_center"]) == 2
    assert phl["default_zoom"] > 0
    assert phl["launch_status"] == "live"
