from collections.abc import Iterator, Sequence
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.db import Base

_MAX_BIND_PARAMS = 30000


def batch_by_bind_limit(
    rows: Sequence[dict[str, Any]], *, max_params: int = _MAX_BIND_PARAMS
) -> Iterator[Sequence[dict[str, Any]]]:
    if not rows:
        return
    params_per_row = max(1, len(rows[0]))
    size = max(1, max_params // params_per_row)
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def dedupe_on_conflict_key(
    rows: Sequence[dict[str, Any]], keys: Sequence[str]
) -> list[dict[str, Any]]:
    collapsed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        collapsed[tuple(row[key] for key in keys)] = row
    return list(collapsed.values())


async def upsert(
    session: AsyncSession,
    model: type[Base],
    rows: Sequence[dict[str, Any]],
    *,
    index_elements: Sequence[str],
    update_columns: Sequence[str] | None = None,
    where: ColumnElement[bool] | None = None,
) -> int:
    if not rows:
        return 0
    rows = dedupe_on_conflict_key(rows, index_elements)
    keys = set(index_elements)
    columns = (
        update_columns
        if update_columns is not None
        else [column for column in rows[0] if column not in keys]
    )
    affected = 0
    for batch in batch_by_bind_limit(rows):
        statement = insert(model).values(list(batch))
        assignments: dict[str, Any] = {column: statement.excluded[column] for column in columns}
        if "updated_at" in model.__table__.columns:
            assignments["updated_at"] = func.now()
        statement = statement.on_conflict_do_update(
            index_elements=list(index_elements), set_=assignments, where=where
        )
        result = cast(CursorResult[Any], await session.execute(statement))
        affected += result.rowcount
    return affected


async def insert_ignore(
    session: AsyncSession,
    model: type[Base],
    rows: Sequence[dict[str, Any]],
    *,
    index_elements: Sequence[str],
) -> int:
    if not rows:
        return 0
    for batch in batch_by_bind_limit(rows):
        statement = (
            insert(model)
            .values(list(batch))
            .on_conflict_do_nothing(index_elements=list(index_elements))
        )
        await session.execute(statement)
    return len(rows)
