from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.policies.models import PolicyDocument
from lotscope.policies.schemas import (
    REQUIRED_POLICIES,
    REQUIRED_SLUGS,
    PolicyRead,
    PolicySummary,
    PolicyWrite,
)


async def _published(session: AsyncSession) -> dict[str, PolicyDocument]:
    rows = (await session.execute(select(PolicyDocument))).scalars()
    return {row.slug: row for row in rows}


async def get_policy(session: AsyncSession, slug: str) -> PolicyRead:
    document = await session.get(PolicyDocument, slug)
    if document is None:
        raise NotFoundError(f"The {slug} policy has not been published yet.")
    return PolicyRead.model_validate(document)


async def list_policies(session: AsyncSession) -> list[PolicySummary]:
    documents = await _published(session)
    return [
        PolicySummary(
            slug=slug,
            title=documents[slug].title if slug in documents else title,
            published=slug in documents,
            version=documents[slug].version if slug in documents else None,
            effective_date=documents[slug].effective_date if slug in documents else None,
        )
        for slug, title in REQUIRED_POLICIES
    ]


async def unpublished_policies(session: AsyncSession) -> list[str]:
    documents = await _published(session)
    return sorted(REQUIRED_SLUGS - documents.keys())


async def publish_policy(session: AsyncSession, slug: str, request: PolicyWrite) -> PolicyRead:
    if slug not in REQUIRED_SLUGS:
        raise ValidationError(f"Unknown policy {slug!r}.")
    document = await session.get(PolicyDocument, slug)
    if document is None:
        document = PolicyDocument(slug=slug)
        session.add(document)
    document.title = request.title
    document.body_markdown = request.body_markdown
    document.version = request.version
    document.effective_date = request.effective_date
    document.published_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(document)
    return PolicyRead.model_validate(document)
