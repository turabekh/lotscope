import importlib
import pkgutil
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, text
from sqlalchemy.ext.asyncio import AsyncSession

import lotscope
from lotscope.core.db import Base
from lotscope.core.market import MARKET_CODE

PARCEL_TABLE = "parcel"

FK_REACHED = "fk"
EXPLICIT_LISTED = "explicit"


@dataclass(frozen=True)
class ExplicitTable:
    key: str
    parcel_column: str
    note: str


EXPLICIT_PARCEL_KEYED_TABLES: tuple[ExplicitTable, ...] = (
    ExplicitTable(
        "parcel_correction",
        "parcel_number",
        "keys on parcel_number but declares a foreign key only to app_user",
    ),
    ExplicitTable(
        "parcel_overlay",
        "parcel_number",
        "overlay membership, rebuilt by a job, no declared foreign key to parcel",
    ),
    ExplicitTable(
        "zba_appeal",
        "parcel_number",
        "appeals reconcile to a parcel by key without a declared foreign key",
    ),
    ExplicitTable("staging.opa", "parcel_number", "ingest landing table, no foreign key to parcel"),
    ExplicitTable("staging.rtt", "parcel_number", "ingest landing table, no foreign key to parcel"),
    ExplicitTable("staging.tax", "parcel_number", "ingest landing table, no foreign key to parcel"),
    ExplicitTable(
        "staging.li_event", "parcel_number", "ingest landing table, no foreign key to parcel"
    ),
    ExplicitTable(
        "staging.sheriff_sale", "parcel_number", "ingest landing table, no foreign key to parcel"
    ),
    ExplicitTable(
        "pre_v11_verdict", "parcel_number", "sweep baseline, no ORM model and no foreign key"
    ),
    ExplicitTable(
        "pre_v11_distress", "parcel_number", "sweep baseline, no ORM model and no foreign key"
    ),
    ExplicitTable(
        "pre_absentee_distress", "parcel_number", "sweep baseline, no ORM model and no foreign key"
    ),
    ExplicitTable(
        "pre_d3_verdict", "parcel_number", "sweep baseline, no ORM model and no foreign key"
    ),
)


@dataclass(frozen=True)
class PurgeTarget:
    key: str
    reason: str
    predicate: str
    note: str = ""

    @property
    def qualified(self) -> str:
        return self.key


def load_full_metadata() -> MetaData:
    for module in pkgutil.iter_modules(lotscope.__path__):
        try:
            importlib.import_module(f"lotscope.{module.name}.models")
        except ModuleNotFoundError:
            continue
    return Base.metadata


def _parcel_predicate(market_code: str) -> str:
    return f"SELECT parcel_number FROM parcel WHERE market_code <> '{market_code}'"


def _child_edges(metadata: MetaData) -> dict[str, list[tuple[str, list[str], list[str]]]]:
    edges: dict[str, list[tuple[str, list[str], list[str]]]] = defaultdict(list)
    for table in metadata.sorted_tables:
        by_parent: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for fk in table.foreign_keys:
            by_parent[fk.column.table.key].append((fk.parent.name, fk.column.name))
        for parent_key, pairs in by_parent.items():
            child_cols = [c for c, _ in pairs]
            parent_cols = [p for _, p in pairs]
            edges[parent_key].append((table.key, child_cols, parent_cols))
    return edges


def _in_predicate(child_cols: list[str], parent: Table, parent_cols: list[str], where: str) -> str:
    lhs = child_cols[0] if len(child_cols) == 1 else "(" + ", ".join(child_cols) + ")"
    projection = ", ".join(parent_cols)
    return f"{lhs} IN (SELECT {projection} FROM {parent.key} WHERE {where})"


def build_deletion_graph(
    metadata: MetaData, *, market_code: str = MARKET_CODE
) -> list[PurgeTarget]:
    edges = _child_edges(metadata)
    parcel_where = f"market_code <> '{market_code}'"
    where_by_key: dict[str, str] = {PARCEL_TABLE: parcel_where}
    reason_by_key: dict[str, str] = {PARCEL_TABLE: FK_REACHED}

    frontier = [PARCEL_TABLE]
    while frontier:
        parent_key = frontier.pop()
        parent = metadata.tables[parent_key]
        for child_key, child_cols, parent_cols in edges.get(parent_key, []):
            if child_key in where_by_key:
                continue
            where_by_key[child_key] = _in_predicate(
                child_cols, parent, parent_cols, where_by_key[parent_key]
            )
            reason_by_key[child_key] = FK_REACHED
            frontier.append(child_key)

    notes: dict[str, str] = {}
    for entry in EXPLICIT_PARCEL_KEYED_TABLES:
        if entry.key in where_by_key:
            continue
        where_by_key[entry.key] = f"{entry.parcel_column} IN ({_parcel_predicate(market_code)})"
        reason_by_key[entry.key] = EXPLICIT_LISTED
        notes[entry.key] = entry.note

    ordered_keys = [t.key for t in metadata.sorted_tables if t.key in where_by_key]
    ordered_keys += [k for k in where_by_key if k not in set(ordered_keys)]
    ordered_keys.reverse()
    ordered_keys = [k for k in ordered_keys if k != PARCEL_TABLE] + [PARCEL_TABLE]

    return [
        PurgeTarget(
            key=key,
            reason=reason_by_key[key],
            predicate=where_by_key[key],
            note=notes.get(key, ""),
        )
        for key in ordered_keys
    ]


async def _table_exists(session: AsyncSession, key: str) -> bool:
    schema, _, name = key.rpartition(".")
    result = await session.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :name"
        ),
        {"schema": schema or "public", "name": name},
    )
    return result.first() is not None


async def count_targets(
    session: AsyncSession, targets: list[PurgeTarget]
) -> list[tuple[PurgeTarget, int | None]]:
    counted: list[tuple[PurgeTarget, int | None]] = []
    for target in targets:
        if not await _table_exists(session, target.key):
            counted.append((target, None))
            continue
        total = await session.scalar(
            text(f"SELECT count(*) FROM {target.key} WHERE {target.predicate}")
        )
        counted.append((target, int(total or 0)))
    return counted


async def delete_targets(
    session: AsyncSession, targets: list[PurgeTarget]
) -> list[tuple[PurgeTarget, int | None]]:
    deleted: list[tuple[PurgeTarget, int | None]] = []
    for target in targets:
        if not await _table_exists(session, target.key):
            deleted.append((target, None))
            continue
        result = await session.execute(text(f"DELETE FROM {target.key} WHERE {target.predicate}"))
        deleted.append((target, result.rowcount))
    return deleted
