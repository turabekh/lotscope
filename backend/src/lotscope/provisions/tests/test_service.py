import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.loader import load_provisions
from lotscope.provisions.service import children_of, find_by_cite

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
