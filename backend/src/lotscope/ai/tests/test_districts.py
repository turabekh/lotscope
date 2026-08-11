import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.districts import (
    GOVERNING_CITES,
    district_anchor_cites,
    district_search_terms,
)
from lotscope.ai.query_terms import extract_districts

pytestmark = pytest.mark.integration

_PROVISION = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES ('phl', :id, :cite, 'code', :kind, "
    ":title_number, null, :ordinal, (:path)::jsonb, :heading, :text, :text, '[]'::jsonb, "
    "'[]'::jsonb, null, 1, 1, 'x.pdf', 'May 25, 2026')"
)
_STANDARD = text(
    "INSERT INTO zoning_standard (market_code, code, code_version, permitted_uses, dimensional) "
    "VALUES ('phl', :code, 'title14-quickguide-2026-02', '[]'::jsonb, '{}'::jsonb)"
)


async def _seed(session: AsyncSession) -> None:
    await session.execute(_STANDARD, {"code": "RSA-5"})
    rows = [
        ("14-701", "14-701", "section", "14", 1, "Dimensional Standards.", "table of standards"),
        ("14-602", "14-602", "section", "14", 2, "Use Tables.", "table of uses"),
        (
            "14-514(5)(a)",
            "14-514(5)(a)",
            "subsection",
            "14",
            3,
            None,
            "In the RSA-5 district, the minimum lot area shall be 1,440 sq. ft.",
        ),
        (
            "9-3010",
            "9-3010",
            "section",
            "9",
            4,
            None,
            "Rentals in the RSA-5 district are licensed separately.",
        ),
    ]
    for provision_id, cite, kind, title_number, ordinal, heading, body in rows:
        await session.execute(
            _PROVISION,
            {
                "id": provision_id,
                "cite": cite,
                "kind": kind,
                "title_number": title_number,
                "ordinal": ordinal,
                "path": json.dumps([title_number, cite]),
                "heading": heading,
                "text": body,
            },
        )
    await session.commit()


async def test_a_district_resolves_to_the_tables_that_actually_govern_it(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await district_anchor_cites(db_session, "RSA-5", market_code="phl")

    assert cites[: len(GOVERNING_CITES)] == list(GOVERNING_CITES)


async def test_district_specific_supplements_ride_along_behind_the_tables(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await district_anchor_cites(db_session, "RSA-5", market_code="phl")

    assert "14-514(5)(a)" in cites


async def test_a_title_scope_keeps_supplements_inside_the_scope(db_session: AsyncSession) -> None:
    await _seed(db_session)

    cites = await district_anchor_cites(db_session, "RSA-5", market_code="phl", titles=["14"])

    assert "9-3010" not in cites


async def test_an_unregistered_district_anchors_nothing_rather_than_guessing(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await district_anchor_cites(db_session, "ZZ-9", market_code="phl")

    assert cites == []


async def test_the_district_is_read_from_the_question_as_written(db_session: AsyncSession) -> None:
    await _seed(db_session)
    districts = extract_districts("can I build on an rsa5 lot?")

    cites = await district_anchor_cites(db_session, districts[0], market_code="phl")

    assert cites[0] == GOVERNING_CITES[0]


async def test_supplements_never_duplicate_a_governing_table(db_session: AsyncSession) -> None:
    await _seed(db_session)

    cites = await district_anchor_cites(db_session, "RSA-5", market_code="phl")

    assert len(cites) == len(set(cites))


def test_a_district_is_searched_in_both_the_written_and_stored_spellings() -> None:
    assert district_search_terms("RSA5") == ["RSA-5", "RSA5"]
    assert district_search_terms("RSA-5") == ["RSA-5", "RSA5"]
    assert district_search_terms("cmx2.5") == ["CMX-2.5", "CMX2.5"]


def test_a_district_with_no_number_is_searched_as_written() -> None:
    assert district_search_terms("ICMX") == ["ICMX"]


async def test_the_stored_unhyphenated_code_finds_the_same_supplements(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    hyphenated = await district_anchor_cites(db_session, "RSA-5", market_code="phl")
    stored = await district_anchor_cites(db_session, "RSA5", market_code="phl")

    assert stored == hyphenated
    assert "14-514(5)(a)" in stored
