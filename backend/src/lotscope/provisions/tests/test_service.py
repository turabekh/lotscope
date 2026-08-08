import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.loader import load_provisions
from lotscope.provisions.service import (
    ancestors_of,
    children_of,
    find_by_cite,
    find_mentioning,
    get_provision,
    refs_of,
    search_ranked,
    siblings_of,
)

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
async def loaded(db_session: AsyncSession, tmp_path: Path) -> AsyncSession:
    target = tmp_path / "phillycode"
    shutil.copytree(FIXTURES, target)
    await load_provisions(db_session, target)
    return db_session


async def test_a_repeated_cite_returns_every_row_in_document_order(loaded: AsyncSession) -> None:
    rows = await find_by_cite(loaded, "phl", "7-101")

    assert [row.id for row in rows] == ["7-101", "7-101~2"]
    assert [row.ordinal for row in rows] == [3, 6]


async def test_an_unknown_cite_returns_an_empty_list(loaded: AsyncSession) -> None:
    assert await find_by_cite(loaded, "phl", "99-999") == []


async def test_a_cite_from_another_market_is_not_returned(loaded: AsyncSession) -> None:
    assert await find_by_cite(loaded, "pgh", "7-101") == []


async def test_children_come_back_ordered_by_ordinal(loaded: AsyncSession) -> None:
    children = await children_of(loaded, "phl", "7-100")

    assert [child.id for child in children] == ["7-101", "7-101~2", "7-102"]
    assert [child.ordinal for child in children] == [3, 6, 7]


async def test_a_leaf_has_no_children(loaded: AsyncSession) -> None:
    assert await children_of(loaded, "phl", "7-101(1)") == []


async def test_get_provision_returns_one_row_or_none(loaded: AsyncSession) -> None:
    found = await get_provision(loaded, "phl", "7-101(1)")

    assert found is not None
    assert found.cite == "7-101(1)"
    assert found.refs == ["7-102"]
    assert await get_provision(loaded, "phl", "does-not-exist") is None
    assert await get_provision(loaded, "pgh", "7-101(1)") is None


async def test_ancestors_come_back_root_first(loaded: AsyncSession) -> None:
    chain = await ancestors_of(loaded, "phl", "7-101(1)")

    assert [item.id for item in chain] == ["7", "7-100", "7-101"]


async def test_a_title_root_has_no_ancestors(loaded: AsyncSession) -> None:
    assert await ancestors_of(loaded, "phl", "7") == []
    assert await ancestors_of(loaded, "phl", "nope") == []


async def test_siblings_exclude_the_provision_itself(loaded: AsyncSession) -> None:
    siblings = await siblings_of(loaded, "phl", "7-101")

    assert [item.id for item in siblings] == ["7-101~2", "7-102"]
    assert await siblings_of(loaded, "phl", "7") == []


async def test_refs_resolve_to_the_provisions_they_cite(loaded: AsyncSession) -> None:
    refs = await refs_of(loaded, "phl", "7-101(1)")

    assert [item.id for item in refs] == ["7-102"]


async def test_a_provision_with_no_refs_resolves_to_nothing(loaded: AsyncSession) -> None:
    assert await refs_of(loaded, "phl", "7-101(2)") == []
    assert await refs_of(loaded, "phl", "nope") == []


async def test_lexical_lookup_finds_provisions_that_mention_a_term(loaded: AsyncSession) -> None:
    hits = await find_mentioning(loaded, "phl", ["fixture subsection"])

    assert [item.id for item in hits] == ["7-101(1)", "7-101(2)"]


async def test_an_exact_cite_outranks_a_caption_that_merely_names_it(
    loaded: AsyncSession,
) -> None:
    hits = await find_mentioning(loaded, "phl", ["7-102"])

    assert hits[0].cite == "7-102"
    assert "7-102#table1" in {item.id for item in hits}


async def test_lexical_lookup_reaches_inside_table_data(loaded: AsyncSession) -> None:
    hits = await find_mentioning(loaded, "phl", ["Single-Family"])

    assert "7-102#table1" in {item.id for item in hits}


async def test_lexical_lookup_can_be_scoped_to_titles(loaded: AsyncSession) -> None:
    assert await find_mentioning(loaded, "phl", ["7-102"], title_numbers=["8.1"]) == []
    assert await find_mentioning(loaded, "phl", ["7-102"], title_numbers=["7"]) != []


async def test_lexical_lookup_with_no_terms_does_not_scan_the_corpus(
    loaded: AsyncSession,
) -> None:
    assert await find_mentioning(loaded, "phl", []) == []


async def test_ranked_search_puts_the_best_lexical_match_first(loaded: AsyncSession) -> None:
    hits = await search_ranked(loaded, "phl", "fixture values table")

    assert hits[0].id == "7-102#table1"


async def test_ranked_search_matches_headings_and_captions_not_only_body(
    loaded: AsyncSession,
) -> None:
    assert [h.id for h in await search_ranked(loaded, "phl", "repeated citation")] == ["7-101~2"]


async def test_ranked_search_can_be_scoped_and_ignores_an_empty_query(
    loaded: AsyncSession,
) -> None:
    assert await search_ranked(loaded, "phl", "   ") == []
    assert await search_ranked(loaded, "phl", "repealed chapter", title_numbers=["7"]) == []
    assert [
        hit.id
        for hit in await search_ranked(loaded, "phl", "repealed chapter", title_numbers=["8.1"])
    ] == ["8.1-100"]
