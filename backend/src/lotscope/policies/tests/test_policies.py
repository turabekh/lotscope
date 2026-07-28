from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.policies.schemas import REQUIRED_SLUGS, PolicyWrite
from lotscope.policies.service import (
    get_policy,
    list_policies,
    publish_policy,
    unpublished_policies,
)

pytestmark = pytest.mark.integration


def _write(version: str = "2026-07-28") -> PolicyWrite:
    return PolicyWrite(
        title="Terms of Service",
        body_markdown="Owner-approved text.",
        version=version,
        effective_date=datetime(2026, 8, 1, tzinfo=UTC),
    )


async def test_an_unpublished_policy_is_absent_not_empty(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await get_policy(db_session, "terms")


async def test_the_index_lists_every_required_policy_as_unpublished(
    db_session: AsyncSession,
) -> None:
    summaries = await list_policies(db_session)
    assert {s.slug for s in summaries} == REQUIRED_SLUGS
    assert all(s.published is False for s in summaries)
    assert all(s.version is None for s in summaries)


async def test_publishing_makes_a_policy_readable(db_session: AsyncSession) -> None:
    await publish_policy(db_session, "terms", _write())
    policy = await get_policy(db_session, "terms")
    assert policy.body_markdown == "Owner-approved text."
    assert policy.version == "2026-07-28"


async def test_republishing_replaces_rather_than_duplicates(db_session: AsyncSession) -> None:
    await publish_policy(db_session, "terms", _write())
    await publish_policy(db_session, "terms", _write(version="2026-09-01"))
    assert (await get_policy(db_session, "terms")).version == "2026-09-01"


async def test_unknown_policies_are_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await publish_policy(db_session, "cookies", _write())


async def test_outstanding_policies_are_reported_for_launch_gating(
    db_session: AsyncSession,
) -> None:
    assert set(await unpublished_policies(db_session)) == REQUIRED_SLUGS
    await publish_policy(db_session, "terms", _write())
    assert "terms" not in await unpublished_policies(db_session)
    assert len(await unpublished_policies(db_session)) == len(REQUIRED_SLUGS) - 1
