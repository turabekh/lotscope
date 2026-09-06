from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_session
from lotscope.diligence.render import render_diligence_pdf
from lotscope.diligence.schemas import DiligenceLine, DiligenceReport


@pytest.fixture
async def diligence_app(
    db_session: AsyncSession, tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[tuple[FastAPI, int, int]]:
    """An app signed in as a buyer with one ready diligence on one parcel."""
    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('gate@example.com', 'x', 'user', 'pro', true)"
        )
    )
    user_id = int(
        await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'gate@example.com'"))
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address) "
            "VALUES ('phl:900000201', 'phl', '1 GATE ST')"
        )
    )

    report = DiligenceReport(
        parcel_number="phl:900000201",
        address="1 GATE ST",
        computed_at=datetime.now(UTC),
        lines=[
            DiligenceLine(
                key="title_chain",
                label="Title chain",
                status="clear",
                evidence="Nothing recorded since our last read.",
                source="rtt_summary",
            )
        ],
    )
    path = tmp_path_factory.mktemp("diligence") / "report.pdf"
    path.write_bytes(render_diligence_pdf(report))

    await db_session.execute(
        text(
            "INSERT INTO diligence_run (user_id, parcel_number, status, pdf_path, "
            "report_json, generated_at) VALUES (:u, 'phl:900000201', 'ready', :p, "
            "CAST(:j AS jsonb), now())"
        ),
        {"u": user_id, "p": str(path), "j": report.model_dump_json()},
    )
    run_id = int(
        await db_session.scalar(
            text("SELECT id FROM diligence_run WHERE user_id = :u"), {"u": user_id}
        )
    )
    await db_session.flush()

    user = await db_session.get(User, user_id)
    assert user is not None

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield app, user_id, run_id
    app.dependency_overrides.clear()
