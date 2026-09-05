"""Make LotScope's stored copy wrong on purpose, then put it back.

The live-verification tasks only test anything if the stored value actually disagrees with
the source. These helpers edit one field, hand the task a snapshot, and restore it afterwards
— running the suite must not leave the local database corrupted.

Only the columns the live tools compare are writable here. A typo in tasks.yaml should fail
loudly, not quietly rewrite something else.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

WRITABLE: dict[str, frozenset[str]] = {
    "parcel": frozenset({"owner", "mailing_address", "market_value", "land_use"}),
    "li_event": frozenset({"status", "case_status"}),
    "sheriff_sale": frozenset({"status", "sale_date"}),
    "sale": frozenset({"document_id", "sale_date", "sale_price", "grantee"}),
}

_PRIMARY_KEY = {
    "parcel": "parcel_number",
    "li_event": "id",
    "sheriff_sale": "id",
    "sale": "id",
}


@dataclass(frozen=True)
class StaleEdit:
    table: str
    where: dict[str, Any]
    set: dict[str, Any]


@dataclass(frozen=True)
class Restore:
    table: str
    key_column: str
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class Planted:
    """What one task changed, and enough to undo every consequence of it."""

    restores: list[Restore]
    parcels: set[str]
    correction_watermark: int


def parse(entries: list[dict[str, Any]] | None) -> list[StaleEdit]:
    edits: list[StaleEdit] = []
    for entry in entries or []:
        table = entry["table"]
        if table not in WRITABLE:
            raise ValueError(f"{table!r} is not a table the eval may edit.")
        unknown = set(entry["set"]) - WRITABLE[table]
        if unknown:
            raise ValueError(f"{table}.{sorted(unknown)} is not an editable column.")
        edits.append(StaleEdit(table=table, where=dict(entry["where"]), set=dict(entry["set"])))
    return edits


def _where_sql(where: dict[str, Any]) -> str:
    return " AND ".join(f"{column} = :w_{column}" for column in where)


def _where_params(where: dict[str, Any]) -> dict[str, Any]:
    return {f"w_{column}": value for column, value in where.items()}


async def apply(session: AsyncSession, edits: list[StaleEdit]) -> Planted:
    restores: list[Restore] = []
    parcels: set[str] = set()
    watermark = int(
        await session.scalar(text("SELECT coalesce(max(id), 0) FROM parcel_correction")) or 0
    )
    for edit in edits:
        key = _PRIMARY_KEY[edit.table]
        columns = ", ".join(sorted({key, *edit.set}))
        before = (
            (
                await session.execute(
                    text(f"SELECT {columns} FROM {edit.table} WHERE {_where_sql(edit.where)}"),
                    _where_params(edit.where),
                )
            )
            .mappings()
            .all()
        )
        if not before:
            raise ValueError(
                f"No {edit.table} row matches {edit.where}; the eval would be a no-op."
            )

        restores.append(Restore(table=edit.table, key_column=key, rows=[dict(r) for r in before]))
        touched = (
            await session.execute(
                text(
                    f"SELECT DISTINCT parcel_number FROM {edit.table} "
                    f"WHERE {_where_sql(edit.where)}"
                ),
                _where_params(edit.where),
            )
        ).scalars()
        parcels.update(value for value in touched if value)
        assignments = ", ".join(f"{column} = :s_{column}" for column in edit.set)
        await session.execute(
            text(f"UPDATE {edit.table} SET {assignments} WHERE {_where_sql(edit.where)}"),
            {**{f"s_{c}": v for c, v in edit.set.items()}, **_where_params(edit.where)},
        )
    await session.commit()
    return Planted(restores=restores, parcels=parcels, correction_watermark=watermark)


async def undo(session: AsyncSession, planted: Planted) -> None:
    """Put the rows back, and withdraw the corrections the planted staleness provoked.

    A correction filed against a disagreement we invented is a false positive: leaving it
    sends someone to triage a problem that does not exist. Corrections filed during the same
    task about *other* parcels are real findings and are left alone.
    """
    for restore in reversed(planted.restores):
        for row in restore.rows:
            columns = [c for c in row if c != restore.key_column]
            assignments = ", ".join(f"{column} = :{column}" for column in columns)
            await session.execute(
                text(
                    f"UPDATE {restore.table} SET {assignments} WHERE {restore.key_column} = :__key"
                ),
                {**{c: row[c] for c in columns}, "__key": row[restore.key_column]},
            )

    if planted.parcels:
        await session.execute(
            text(
                "DELETE FROM parcel_correction WHERE id > :watermark "
                "AND parcel_number = ANY(:parcels)"
            ),
            {"watermark": planted.correction_watermark, "parcels": sorted(planted.parcels)},
        )
    await session.commit()
