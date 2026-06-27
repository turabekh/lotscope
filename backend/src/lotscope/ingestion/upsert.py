from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.db import Base


async def upsert(
    session: AsyncSession,
    model: type[Base],
    rows: Sequence[dict[str, Any]],
    *,
    index_elements: Sequence[str],
    update_columns: Sequence[str] | None = None,
) -> int:
    if not rows:
        return 0
    keys = set(index_elements)
    statement = insert(model).values(list(rows))
    columns = update_columns if update_columns is not None else [
        column for column in rows[0] if column not in keys
    ]
    assignments: dict[str, Any] = {column: statement.excluded[column] for column in columns}
    if "updated_at" in model.__table__.columns:
        assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        index_elements=list(index_elements), set_=assignments
    )
    await session.execute(statement)
    return len(rows)
