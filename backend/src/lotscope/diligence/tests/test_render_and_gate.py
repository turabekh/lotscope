"""The PDF opens, says what it found, and only reaches a buyer who may have it."""

import io
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.diligence.render import diligence_filename, render_diligence_pdf
from lotscope.diligence.schemas import DiligenceLine, DiligenceReport

_NOW = datetime(2026, 9, 6, 12, 30, tzinfo=UTC)


def _report() -> DiligenceReport:
    return DiligenceReport(
        parcel_number="phl:463278700",
        address="902 S CECIL ST",
        computed_at=_NOW,
        lines=[
            DiligenceLine(
                key="title_chain",
                label="Title chain",
                status="clear",
                evidence="The live deed index agrees with our copy across 3 transfers.",
                source="rtt_summary (live)",
                source_url="https://phl.carto.com/api/v2/sql?q=x",
                fetched_at=_NOW,
            ),
            DiligenceLine(
                key="delinquency",
                label="Tax delinquency and the named debtor",
                status="flag",
                evidence="Delinquent: 5392.54 due, against JONES LOUIS, not the current owner.",
                source="tax_status",
                ingested_at=_NOW,
            ),
            DiligenceLine(
                key="conservatorship",
                label="Act 135 conservatorship",
                status="unverified",
                evidence="Not in our data — check the Court of Common Pleas docket.",
                source="none",
            ),
        ],
    )


def _text() -> str:
    reader = PdfReader(io.BytesIO(render_diligence_pdf(_report())))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_the_pdf_opens_and_carries_every_status() -> None:
    data = render_diligence_pdf(_report())
    assert data.startswith(b"%PDF")

    text = _text()
    assert "Lot Diligence - 902 S CECIL ST" in text
    # The status column is the page: a reader must see all three without reading prose.
    for marker in ("CLEAR", "FLAG", "UNVERIFIED"):
        assert marker in text, marker
    assert "1 flagged, 1 unverified" in text


def test_every_line_prints_where_it_came_from_and_when() -> None:
    text = _text()

    assert "read live 2026-09-06 12:30 UTC" in text
    assert "our copy, ingested 2026-09-06" in text
    assert "no as-of recorded" in text


def test_the_pdf_names_what_it_cannot_see_before_the_buyer_closes() -> None:
    text = _text()

    assert "Before you close" in text
    assert "title search" in text
    assert "PGW" in text


def test_the_filename_names_the_parcel() -> None:
    assert diligence_filename("phl:463278700") == "lotscope-diligence-phl-463278700.pdf"


@pytest.mark.integration
async def test_the_download_is_gated_until_it_is_bought(
    db_session: AsyncSession, diligence_app: tuple[FastAPI, int, int]
) -> None:
    app, _user_id, run_id = diligence_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        refused = await client.get(f"/diligence/{run_id}/download")
    assert refused.status_code == 402
    assert "199" in refused.json()["detail"]


@pytest.mark.integration
async def test_a_paid_parcel_downloads(
    db_session: AsyncSession, diligence_app: tuple[FastAPI, int, int]
) -> None:
    app, user_id, run_id = diligence_app
    await db_session.execute(
        text(
            "INSERT INTO purchase (user_id, sku, stripe_session_id, object_ref, "
            "amount_cents, paid_at) VALUES (:u, 'diligence', :s, 'phl:900000201', 19900, now())"
        ),
        {"u": user_id, "s": f"cs_test_{user_id}"},
    )
    await db_session.flush()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.get(f"/diligence/{run_id}/download")

    assert allowed.status_code == 200
    assert allowed.headers["content-type"] == "application/pdf"
    assert allowed.content.startswith(b"%PDF")


@pytest.mark.integration
async def test_a_comped_buyer_downloads_without_paying(
    db_session: AsyncSession, diligence_app: tuple[FastAPI, int, int]
) -> None:
    app, user_id, run_id = diligence_app
    await db_session.execute(
        text("UPDATE app_user SET comp_until = now() + interval '30 days' WHERE id = :u"),
        {"u": user_id},
    )
    await db_session.flush()
    # The request holds the user object the fixture loaded, so it has to see the comp.
    user = await db_session.get(User, user_id)
    assert user is not None
    await db_session.refresh(user)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        allowed = await client.get(f"/diligence/{run_id}/download")

    assert allowed.status_code == 200
