from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient, quote_literal
from lotscope.ingestion.reconciliation import to_parcel_key

DEFAULT_SAMPLE = 50
_RELATIVE_TOLERANCE = 0.005


@dataclass(frozen=True)
class FieldPair:
    stored_column: str
    upstream_column: str
    numeric: bool = False


FIELD_PAIRS: tuple[FieldPair, ...] = (
    FieldPair("owner", "owner_1"),
    FieldPair("address", "location"),
    FieldPair("base_zoning_code", "zoning"),
    FieldPair("market_value", "market_value", numeric=True),
    FieldPair("lot_area_sqft", "total_area", numeric=True),
)


@dataclass(frozen=True)
class FieldDrift:
    parcel_number: str
    field: str
    stored: str | None
    upstream: str | None


@dataclass
class ReconciliationReport:
    sampled: int = 0
    compared: int = 0
    absent_upstream: list[str] = field(default_factory=list)
    drifted: list[FieldDrift] = field(default_factory=list)

    @property
    def drifted_parcels(self) -> set[str]:
        return {item.parcel_number for item in self.drifted}

    @property
    def agreement(self) -> float:
        if self.compared == 0:
            return 0.0
        return 1.0 - len(self.drifted_parcels) / self.compared


_SAMPLE_SQL = text(
    "SELECT parcel_number, owner, address, base_zoning_code, market_value, lot_area_sqft "
    "FROM parcel WHERE market_code = 'phl' AND source = 'opa_properties_public' "
    "ORDER BY random() LIMIT :limit"
)


def _normalise(value: Any, numeric: bool) -> str | None:
    if value is None:
        return None
    if numeric:
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return None
    text_value = " ".join(str(value).split()).upper()
    return text_value or None


def _matches(stored: Any, upstream: Any, numeric: bool) -> bool:
    left = _normalise(stored, numeric)
    right = _normalise(upstream, numeric)
    if left == right:
        return True
    if not numeric or left is None or right is None:
        return False
    scale = max(abs(float(left)), abs(float(right)))
    return abs(float(left) - float(right)) <= _RELATIVE_TOLERANCE * scale


def compare_rows(
    stored: dict[str, Any],
    upstream: dict[str, Any],
    pairs: tuple[FieldPair, ...] = FIELD_PAIRS,
) -> list[FieldDrift]:
    parcel_number = str(stored["parcel_number"])
    drift: list[FieldDrift] = []
    for pair in pairs:
        stored_value = stored.get(pair.stored_column)
        upstream_value = upstream.get(pair.upstream_column)
        if not _matches(stored_value, upstream_value, pair.numeric):
            drift.append(
                FieldDrift(
                    parcel_number=parcel_number,
                    field=pair.stored_column,
                    stored=_normalise(stored_value, pair.numeric),
                    upstream=_normalise(upstream_value, pair.numeric),
                )
            )
    return drift


def upstream_query(opa_numbers: list[str]) -> str:
    columns = ", ".join(sorted({"parcel_number", *(pair.upstream_column for pair in FIELD_PAIRS)}))
    keys = ", ".join(quote_literal(number) for number in opa_numbers)
    return f"SELECT {columns} FROM opa_properties_public WHERE parcel_number IN ({keys})"


async def reconcile_against_opa(
    session: AsyncSession, carto: CartoClient, *, sample: int = DEFAULT_SAMPLE
) -> ReconciliationReport:
    rows = (await session.execute(_SAMPLE_SQL, {"limit": sample})).mappings().all()
    report = ReconciliationReport(sampled=len(rows))
    if not rows:
        return report

    stored_by_key = {str(row["parcel_number"]): dict(row) for row in rows}
    opa_numbers = [key.split(":", 1)[-1] for key in stored_by_key]
    upstream_rows = await carto.query(upstream_query(opa_numbers))
    upstream_by_key = {
        key: row for row in upstream_rows if (key := to_parcel_key(row.get("parcel_number")))
    }

    for key, stored in stored_by_key.items():
        upstream = upstream_by_key.get(key)
        if upstream is None:
            report.absent_upstream.append(key)
            continue
        report.compared += 1
        report.drifted.extend(compare_rows(stored, upstream))
    return report
