"""What the checklist says about three lots, and what it refuses to say about any of them."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.diligence.schemas import CHECK_KEYS, DiligenceLine, DiligenceReport
from lotscope.diligence.service import build_diligence

pytestmark = pytest.mark.integration

_GEOM = "ST_GeomFromText('POLYGON((0 0,0 20,20 20,20 0,0 0))', 2272)"
_TOUCHING = "ST_GeomFromText('POLYGON((20 0,20 20,40 20,40 0,20 0))', 2272)"


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'pro', true)"
        ),
        {"e": email},
    )
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email = :e"), {"e": email}))


async def _parcel(
    session: AsyncSession,
    number: str,
    *,
    owner: str = "ACME LAND LLC",
    geom: str = _GEOM,
    vacant: bool = True,
    city_owned: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, owner, is_vacant, "
            f"is_city_owned, lot_area_sqft, base_zoning_code, geom_local) VALUES "
            f"(:pn, 'phl', :addr, :owner, :vacant, :city, 1600, 'RSA-5', {geom})"
        ),
        {
            "pn": number,
            "addr": f"{number[-4:]} TEST ST",
            "owner": owner,
            "vacant": vacant,
            "city": city_owned,
        },
    )


def _by_key(report: DiligenceReport) -> dict[str, DiligenceLine]:
    return {line.key: line for line in report.lines}


async def test_a_clean_parcel_reads_clear_but_never_silent(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "clean@example.com")
    await _parcel(db_session, "phl:900000101")
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
            "sale_price, grantor, grantee) VALUES ('phl:900000101', 'D1', 'DEED', "
            "'2024-05-01', 50000, 'PRIOR OWNER LLC', 'ACME LAND LLC')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, as_of_date) "
            "VALUES ('phl:900000101', false, 0, '2026-01-31')"
        )
    )
    await db_session.flush()

    report = await build_diligence(db_session, "phl:900000101", user_id=user_id)

    assert report is not None
    # Every check appears on every report, in the same order.
    assert [line.key for line in report.lines] == list(CHECK_KEYS)
    lines = _by_key(report)
    assert lines["delinquency"].status == "clear"
    assert lines["adjacent_unsafe"].status == "clear"
    # The two we have no source for say so, and say where to go instead.
    assert lines["conservatorship"].status == "unverified"
    assert "Court of Common Pleas" in lines["conservatorship"].evidence
    assert lines["utilities_curb"].status == "unverified"
    assert "Not in our data" in lines["utilities_curb"].evidence
    assert "Water Revenue and PGW" in report.closing


async def test_an_open_case_and_a_public_neighbour_are_both_flagged(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "flagged@example.com")
    await _parcel(db_session, "phl:900000102")
    await _parcel(
        db_session,
        "phl:900000103",
        owner="CITY OF PHILADELPHIA",
        geom=_TOUCHING,
        vacant=False,
        city_owned=True,
    )
    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, status, "
            "case_status, event_date, description, is_unsafe, is_imminently_dangerous) VALUES "
            "('phl:900000102', 'V1', 'violation', 'OPEN', 'IN VIOLATION', current_date, "
            "'Vacant lot not maintained', false, false), "
            "('phl:900000103', 'V2', 'violation', 'OPEN', 'IN VIOLATION', current_date, "
            "'IMMINENTLY DANGEROUS', true, true)"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "as_of_date, delinquency_owner) VALUES ('phl:900000102', true, 8400, 3, "
            "'2026-01-31', 'PRIOR OWNER LLC')"
        )
    )
    await db_session.flush()

    report = await build_diligence(db_session, "phl:900000102", user_id=user_id)

    assert report is not None
    lines = _by_key(report)
    assert lines["delinquency"].status == "flag"
    assert "PRIOR OWNER LLC" in lines["delinquency"].evidence
    assert lines["adjacent_unsafe"].status == "flag"
    assert "imminently dangerous" in lines["adjacent_unsafe"].evidence
    assert lines["public_neighbour"].status == "flag"
    assert "Land Bank" in lines["public_neighbour"].evidence
    # A built neighbour sharing a boundary is where a party wall would be.
    assert lines["party_wall"].status == "flag"
    assert report.flags >= 4


async def test_estate_language_in_the_grantor_is_a_probate_flag(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "probate@example.com")
    await _parcel(db_session, "phl:900000104", owner="EAEAL 1300 LLC")
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
            "sale_price, grantor, grantee) VALUES ('phl:900000104', 'D9', 'DEED', "
            "'2026-06-29', 61000, 'JONES LOUIS ESTATE OF', 'EAEAL 1300 LLC')"
        )
    )
    await db_session.flush()

    report = await build_diligence(db_session, "phl:900000104", user_id=user_id)

    assert report is not None
    lines = _by_key(report)
    assert lines["estate_probate"].status == "flag"
    assert "JONES LOUIS ESTATE OF" in lines["estate_probate"].evidence
    assert "letters testamentary" in lines["estate_probate"].evidence


async def test_a_parcel_with_no_recorded_transfer_is_unverified_not_clear(
    db_session: AsyncSession,
) -> None:
    """A gap in the chain is not a clean chain, and the line must not read as one."""
    user_id = await _user(db_session, "gap@example.com")
    await _parcel(db_session, "phl:900000105")
    await db_session.flush()

    report = await build_diligence(db_session, "phl:900000105", user_id=user_id)

    assert report is not None
    lines = _by_key(report)
    assert lines["title_chain"].status == "unverified"
    assert "not the same as a clean chain" in lines["title_chain"].evidence
    assert lines["estate_probate"].status == "unverified"


async def test_a_parcel_we_do_not_hold_has_no_report(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "missing@example.com")
    assert await build_diligence(db_session, "phl:999999999", user_id=user_id) is None


async def test_every_line_carries_a_source_and_a_status(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "provenance@example.com")
    await _parcel(db_session, "phl:900000106")
    await db_session.flush()

    report = await build_diligence(db_session, "phl:900000106", user_id=user_id)

    assert report is not None
    for line in report.lines:
        assert line.status in {"clear", "flag", "unverified"}
        assert line.source, line.key
        assert line.evidence.strip(), line.key
        # A line cannot claim both provenances: a reader deciding whether to trust it
        # needs to know whether it was read live or came from our copy.
        assert not (line.fetched_at is not None and line.ingested_at is not None), line.key
    # The two lines with no source at all name themselves as such rather than borrowing one.
    sourceless = {line.key for line in report.lines if line.source == "none"}
    assert sourceless == {"conservatorship", "utilities_curb"}
