from datetime import date

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.extract import ExtractClient
from lotscope.ingestion.loaders.hbg_taxclaim import (
    classify_tax_claim_row,
    load_hbg_tax_claim,
    tax_status_row,
)
from lotscope.ingestion.models import DatasetFreshness

_LIST_DATE = date(2026, 8, 15)


def test_classify_normalizes_key_and_known_types() -> None:
    assert classify_tax_claim_row({"parcel_id": "09001001", "sale_type": "Upset"}) == {
        "parcel_number": "hbg:09-001-001",
        "sale_type": "upset",
        "amount_due": None,
    }
    assert classify_tax_claim_row({"parcel_id": "bad", "sale_type": "upset"}) is None
    assert classify_tax_claim_row({"parcel_id": "09-001-001", "sale_type": "mortgage"}) is None


def test_tax_status_row_only_for_forced_sale_types() -> None:
    upset = {"parcel_number": "hbg:09-001-001", "sale_type": "upset", "amount_due": 4520.11}
    row = tax_status_row(upset, _LIST_DATE)
    assert row is not None
    assert row["in_sheriff_sale"] is True
    assert row["is_delinquent"] is True
    assert row["total_due"] == 4520.11
    assert row["as_of_date"] == _LIST_DATE

    repo = {"parcel_number": "hbg:09-001-001", "sale_type": "repository", "amount_due": 0.0}
    assert tax_status_row(repo, _LIST_DATE) is None


_CSV = (
    b"parcel_id,sale_type,amount_due\n"
    b"04-038-028,upset,4520.11\n"
    b"09-001-001,judicial,8900\n"
    b"13-003-100,repository,0\n"
    b"99-999-999,upset,100\n"
)


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


@pytest.mark.integration
async def test_load_hbg_tax_claim_flags_forced_sale_and_labels_freshness(
    db_session: AsyncSession,
) -> None:
    for local in ("04-038-028", "09-001-001", "13-003-100"):
        await db_session.execute(
            text(f"INSERT INTO parcel (parcel_number, market_code) VALUES ('hbg:{local}', 'hbg')")
        )
    await db_session.flush()

    def _handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_CSV)

    async with ExtractClient(_settings(), transport=httpx.MockTransport(_handler)) as extract:
        total = await load_hbg_tax_claim(
            db_session, extract, list_url="https://x.test/upset.csv", list_date=_LIST_DATE
        )
    # upset + judicial land; repository does not; unknown parcel 99-... has no parcel row
    assert total == 2

    rows = (
        await db_session.execute(
            text(
                "SELECT parcel_number, in_sheriff_sale, is_delinquent FROM tax_status "
                "WHERE parcel_number LIKE 'hbg:%' ORDER BY parcel_number"
            )
        )
    ).all()
    flagged = {r.parcel_number for r in rows if r.in_sheriff_sale}
    assert flagged == {"hbg:04-038-028", "hbg:09-001-001"}

    fresh = await db_session.get(DatasetFreshness, ("hbg", "dc_tax_claim"))
    assert fresh is not None
    assert fresh.detail == "as of 2026-08-15"


def test_repository_rows_extracted_for_public_inventory() -> None:
    from lotscope.ingestion.loaders.hbg_taxclaim import (
        classify_tax_claim_row,
        repository_parcel_numbers,
    )

    rows = [
        {"parcel_id": "01-002-003", "sale_type": "repository", "amount_due": "$0"},
        {"parcel_id": "04-038-028", "sale_type": "upset", "amount_due": "$5,000"},
    ]
    classified = [c for r in rows if (c := classify_tax_claim_row(r)) is not None]
    repo = repository_parcel_numbers(classified)
    assert repo == ["hbg:01-002-003"]


def test_forced_sale_surface_label_market_aware() -> None:
    from lotscope.markets.capabilities import forced_sale_surface_label

    assert forced_sale_surface_label("phl") == "Sheriff sales"
    assert forced_sale_surface_label("hbg") == "Tax sales"
