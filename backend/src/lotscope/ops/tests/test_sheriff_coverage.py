from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import (
    get_current_user,
    get_session,
    get_sheriff_coverage_source,
)
from lotscope.core.config import Settings
from lotscope.ingestion.loaders.sheriff_civilview import CivilViewListRow, CivilViewSheriffSource
from lotscope.ops.service import summarize_sheriff_coverage

_LIST_FIXTURE = (
    Path(__file__).parents[2]
    / "ingestion"
    / "tests"
    / "fixtures"
    / "civilview"
    / "list_county60.html"
)
_CHECKED_AT = datetime(2026, 7, 12, tzinfo=UTC)


def test_summarize_counts_reconciled_and_unreconciled() -> None:
    rows = [
        CivilViewListRow(property_id="1", opa_number="191165600"),
        CivilViewListRow(property_id="2", opa_number="242181300"),
        CivilViewListRow(property_id="3", opa_number="999999999"),
        CivilViewListRow(property_id="4", opa_number=None),
        CivilViewListRow(property_id="5", opa_number="191165600"),
    ]
    existing = {"phl:191165600", "phl:242181300"}
    coverage = summarize_sheriff_coverage(rows, existing, market_code="phl", checked_at=_CHECKED_AT)
    assert coverage.total_listings == 5
    assert coverage.without_opa == 1
    assert coverage.with_opa == 4
    assert coverage.unique_parcels == 3
    assert coverage.reconciled == 2
    assert coverage.unreconciled == 1
    assert coverage.coverage_pct == 66.7
    assert coverage.sample_unreconciled == ["phl:999999999"]
    assert coverage.checked_at == _CHECKED_AT


def test_summarize_handles_empty_list() -> None:
    coverage = summarize_sheriff_coverage([], set(), market_code="phl", checked_at=_CHECKED_AT)
    assert coverage.total_listings == 0
    assert coverage.coverage_pct is None
    assert coverage.sample_unreconciled == []


def _list_source() -> CivilViewSheriffSource:
    html = _LIST_FIXTURE.read_text(encoding="utf-8")

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    return CivilViewSheriffSource(
        Settings(_env_file=None, http_backoff_seconds=0.0),
        transport=httpx.MockTransport(_handler),
    )


def _admin_app(db_session: AsyncSession, *, role: str = "admin") -> FastAPI:
    app = create_app()

    async def _session() -> Any:
        yield db_session

    def _user() -> Any:
        return SimpleNamespace(id=1, role=role)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_sheriff_coverage_source] = _list_source
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.integration
async def test_coverage_endpoint_reconciles_against_parcels(db_session: AsyncSession) -> None:
    for opa in ("191165600", "242181300"):
        await db_session.execute(
            text("INSERT INTO parcel (parcel_number, market_code) VALUES (:pn, 'phl')"),
            {"pn": f"phl:{opa}"},
        )
    await db_session.flush()

    app = _admin_app(db_session)
    async with _client(app) as client:
        resp = await client.post("/admin/ops/sheriff-coverage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["market_code"] == "phl"
    assert body["total_listings"] == 6
    assert body["unique_parcels"] == 6
    assert body["reconciled"] == 2
    assert body["unreconciled"] == 4
    assert body["coverage_pct"] == 33.3
    assert set(body["sample_unreconciled"]).isdisjoint({"phl:191165600", "phl:242181300"})


@pytest.mark.integration
async def test_coverage_endpoint_requires_admin(db_session: AsyncSession) -> None:
    app = _admin_app(db_session, role="user")
    async with _client(app) as client:
        resp = await client.post("/admin/ops/sheriff-coverage")
    assert resp.status_code == 403
