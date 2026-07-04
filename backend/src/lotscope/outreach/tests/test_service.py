import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.service import list_mail_recipients
from lotscope.outreach.schemas import MailMergeRequest
from lotscope.outreach.service import DEFAULT_MESSAGE, merge_message, render_letter_campaign


def test_merge_message_substitutes_all_placeholders() -> None:
    result = merge_message(
        "Hi {owner}, about {property_address} ({parcel_number}).",
        owner="Jane Doe",
        property_address="1 Main St",
        parcel_number="000000001",
    )
    assert result == "Hi Jane Doe, about 1 Main St (000000001)."


def test_merge_message_falls_back_when_address_missing() -> None:
    result = merge_message(
        DEFAULT_MESSAGE, owner="Jane", property_address=None, parcel_number="000000001"
    )
    assert "the property" in result
    assert "{property_address}" not in result
    assert "{owner}" not in result


async def _seed_lead(
    session: AsyncSession,
    parcel_number: str,
    *,
    owner: str | None,
    mailing: str | None,
    score: int = 80,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, owner, mailing_address, is_vacant) "
            "VALUES (:pn, :addr, :owner, :mailing, true)"
        ),
        {
            "pn": parcel_number,
            "addr": f"{parcel_number} Main St",
            "owner": owner,
            "mailing": mailing,
        },
    )
    await session.execute(
        text(
            "INSERT INTO parcel_distress (parcel_number, score, tier, version) "
            "VALUES (:pn, :score, 'high', 'v2')"
        ),
        {"pn": parcel_number, "score": score},
    )


@pytest.mark.integration
async def test_recipients_require_owner_and_mailing_address(db_session: AsyncSession) -> None:
    await _seed_lead(db_session, "000000001", owner="Jane Doe", mailing="PO Box 1")
    await _seed_lead(db_session, "000000002", owner="No Mail", mailing=None)
    await _seed_lead(db_session, "000000003", owner=None, mailing="PO Box 3")
    await db_session.flush()

    recipients = await list_mail_recipients(db_session, row_limit=100, min_score=1)
    assert [r.parcel_number for r in recipients] == ["000000001"]
    assert recipients[0].owner == "Jane Doe"


@pytest.mark.integration
async def test_render_letter_campaign_returns_pdf(db_session: AsyncSession) -> None:
    await _seed_lead(db_session, "000000001", owner="Jane Doe", mailing="PO Box 1")
    await _seed_lead(db_session, "000000002", owner="John Roe", mailing="PO Box 2")
    await db_session.flush()

    request = MailMergeRequest(from_name="Sam Buyer", from_contact="555-0100")
    pdf = await render_letter_campaign(db_session, request, row_limit=100)
    assert pdf is not None
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


@pytest.mark.integration
async def test_render_letter_campaign_none_without_recipients(db_session: AsyncSession) -> None:
    await _seed_lead(db_session, "000000001", owner="Jane", mailing="PO Box 1", score=10)
    await db_session.flush()

    request = MailMergeRequest(from_name="Sam", from_contact="x", min_score=90)
    assert await render_letter_campaign(db_session, request, row_limit=100) is None


@pytest.mark.integration
async def test_recipients_dedupe_by_owner_keeps_top_scored(db_session: AsyncSession) -> None:
    await _seed_lead(db_session, "000000001", owner="ACME LLC", mailing="PO Box 9", score=90)
    await _seed_lead(db_session, "000000002", owner="acme llc", mailing="po box 9", score=60)
    await _seed_lead(db_session, "000000003", owner="Other Owner", mailing="PO Box 8", score=70)
    await db_session.flush()

    deduped = await list_mail_recipients(db_session, row_limit=100, min_score=1, one_per_owner=True)
    owners = sorted(r.owner for r in deduped)
    assert owners == ["ACME LLC", "Other Owner"]
    acme = next(r for r in deduped if r.owner == "ACME LLC")
    assert acme.parcel_number == "000000001"

    all_rows = await list_mail_recipients(db_session, row_limit=100, min_score=1)
    assert len(all_rows) == 3


@pytest.mark.integration
async def test_render_letter_campaign_respects_row_limit(db_session: AsyncSession) -> None:
    for i in range(1, 4):
        await _seed_lead(db_session, f"00000000{i}", owner=f"Owner {i}", mailing=f"PO Box {i}")
    await db_session.flush()

    recipients = await list_mail_recipients(db_session, row_limit=2, min_score=1)
    assert len(recipients) == 2
