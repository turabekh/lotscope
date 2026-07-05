from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assemblage.logic import (
    NeighborSignal,
    TargetLot,
    assess_potential,
    build_reasons,
    classify_acquirability,
    is_candidate,
    summarize,
)
from lotscope.assemblage.models import ParcelAssemblage
from lotscope.assemblage.schemas import (
    AdjacentLot,
    AssemblageResult,
    AssemblageSummary,
    AssemblageTopPlay,
    AssemblageTopResponse,
    Potential,
)
from lotscope.zoning.service import assemblage_unit_estimate

_ADJACENCY_TOLERANCE_FT = 2.0
_NEIGHBOR_LIMIT = 16

_TARGET_SQL = text(
    "SELECT owner, base_zoning_code, lot_area_sqft, frontage_ft, "
    "(geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_NEIGHBORS_SQL = text(
    "WITH t AS ("
    "  SELECT owner, base_zoning_code, geom_local, market_code "
    "  FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT n.parcel_number, n.address, n.owner, n.base_zoning_code, n.lot_area_sqft, "
    "n.frontage_ft, n.market_value, n.is_vacant, n.is_city_owned, "
    "(n.owner IS NOT NULL AND t.owner IS NOT NULL "
    " AND lower(btrim(n.owner)) = lower(btrim(t.owner))) AS same_owner, "
    "(n.base_zoning_code IS NOT NULL AND t.base_zoning_code IS NOT NULL "
    " AND upper(replace(n.base_zoning_code, '-', '')) = upper(replace(t.base_zoning_code, '-', ''))"
    ") AS same_zoning, "
    "ST_Length(ST_CollectionExtract(ST_Intersection(n.geom_local, t.geom_local), 2)) "
    "AS shared_boundary_ft "
    "FROM t JOIN parcel n ON n.parcel_number <> :parcel_number AND n.geom_local IS NOT NULL "
    "AND n.market_code = t.market_code "
    "AND ST_DWithin(n.geom_local, t.geom_local, :tolerance) "
    "ORDER BY same_owner DESC, n.is_vacant DESC NULLS LAST, shared_boundary_ft DESC NULLS LAST "
    "LIMIT :limit"
)

_SOURCES: list[dict[str, Any]] = [
    {"source": "pwd_parcel", "field": "geom_local"},
    {"source": "opa_properties", "field": "owner"},
]


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _signal(row: Row[Any]) -> NeighborSignal:
    return NeighborSignal(
        parcel_number=row.parcel_number,
        same_owner=bool(row.same_owner),
        same_zoning=bool(row.same_zoning),
        is_vacant=bool(row.is_vacant),
        is_city_owned=bool(row.is_city_owned),
        lot_area_sqft=_as_float(row.lot_area_sqft),
        frontage_ft=_as_float(row.frontage_ft),
    )


def _adjacent_lot(row: Row[Any], signal: NeighborSignal) -> AdjacentLot:
    return AdjacentLot(
        parcel_number=row.parcel_number,
        address=row.address,
        owner=row.owner,
        base_zoning_code=row.base_zoning_code,
        lot_area_sqft=_as_float(row.lot_area_sqft),
        frontage_ft=_as_float(row.frontage_ft),
        market_value=_as_float(row.market_value),
        is_vacant=row.is_vacant,
        is_city_owned=row.is_city_owned,
        same_owner=signal.same_owner,
        same_zoning=signal.same_zoning,
        shared_boundary_ft=_as_float(row.shared_boundary_ft),
        acquirability=classify_acquirability(signal),
        is_candidate=is_candidate(signal),
    )


def _result(
    parcel_number: str,
    potential: Potential,
    summary: AssemblageSummary,
    neighbors: list[AdjacentLot],
    reasons: list[str],
    computed_at: datetime,
) -> AssemblageResult:
    return AssemblageResult(
        parcel_number=parcel_number,
        potential=potential,
        summary=summary,
        neighbors=neighbors,
        reasons=reasons,
        sources=_SOURCES,
        computed_at=computed_at,
    )


async def compute_assemblage(session: AsyncSession, parcel_number: str) -> AssemblageResult | None:
    target_row = (
        await session.execute(_TARGET_SQL, {"parcel_number": parcel_number})
    ).one_or_none()
    if target_row is None:
        return None
    computed_at = datetime.now(UTC)
    target = TargetLot(
        lot_area_sqft=_as_float(target_row.lot_area_sqft),
        frontage_ft=_as_float(target_row.frontage_ft),
    )

    if not target_row.has_geometry:
        return _result(
            parcel_number,
            "none",
            AssemblageSummary(
                **vars(summarize(target, [])),
                by_right_units_current=None,
                by_right_units_combined=None,
                units_basis=None,
            ),
            [],
            ["This parcel has no boundary geometry, so adjacent lots cannot be detected."],
            computed_at,
        )

    rows = (
        await session.execute(
            _NEIGHBORS_SQL,
            {
                "parcel_number": parcel_number,
                "tolerance": _ADJACENCY_TOLERANCE_FT,
                "limit": _NEIGHBOR_LIMIT,
            },
        )
    ).all()
    signals = [_signal(row) for row in rows]
    neighbors = [_adjacent_lot(row, signal) for row, signal in zip(rows, signals, strict=True)]
    logic_summary = summarize(target, signals)
    units_current, units_combined, units_basis = await assemblage_unit_estimate(
        session,
        parcel_number,
        current_area_sqft=target.lot_area_sqft,
        combined_area_sqft=logic_summary.combined_lot_area_sqft,
    )
    summary = AssemblageSummary(
        **vars(logic_summary),
        by_right_units_current=units_current,
        by_right_units_combined=units_combined,
        units_basis=units_basis,
    )
    return _result(
        parcel_number,
        assess_potential(signals),
        summary,
        neighbors,
        build_reasons(target, signals),
        computed_at,
    )


_META_SQL = text(
    "SELECT p.base_zoning_code, "
    "(SELECT n.name FROM neighborhood n "
    " WHERE p.geom_local IS NOT NULL AND n.market_code = p.market_code "
    " AND ST_Contains(n.geom_local, ST_Centroid(p.geom_local)) "
    " LIMIT 1) AS neighborhood "
    "FROM parcel p WHERE p.parcel_number = :parcel_number"
)
_DELETE_ASSEMBLAGE_SQL = text("DELETE FROM parcel_assemblage WHERE parcel_number = :parcel_number")


def _unit_unlock(summary: AssemblageSummary) -> int | None:
    current = summary.by_right_units_current
    combined = summary.by_right_units_combined
    if current is None or combined is None:
        return None
    return combined - current


async def _persist_assemblage(
    session: AsyncSession, parcel_number: str, result: AssemblageResult, meta: Row[Any] | None
) -> None:
    values: dict[str, Any] = {
        "parcel_number": parcel_number,
        "potential": result.potential,
        "candidate_count": result.summary.candidate_count,
        "combined_lot_area_sqft": result.summary.combined_lot_area_sqft,
        "by_right_units_current": result.summary.by_right_units_current,
        "by_right_units_combined": result.summary.by_right_units_combined,
        "unit_unlock": _unit_unlock(result.summary),
        "base_zoning_code": meta.base_zoning_code if meta is not None else None,
        "neighborhood": meta.neighborhood if meta is not None else None,
        "sources": result.sources,
        "computed_at": result.computed_at,
    }
    statement = insert(ParcelAssemblage).values(values)
    assignments: dict[str, Any] = {
        column: statement.excluded[column] for column in values if column != "parcel_number"
    }
    assignments["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(index_elements=["parcel_number"], set_=assignments)
    await session.execute(statement)


async def recompute_assemblage(session: AsyncSession, parcel_numbers: Sequence[str]) -> int:
    count = 0
    for parcel_number in parcel_numbers:
        result = await compute_assemblage(session, parcel_number)
        if result is None:
            continue
        if result.summary.candidate_count >= 1:
            meta = (
                await session.execute(_META_SQL, {"parcel_number": parcel_number})
            ).one_or_none()
            await _persist_assemblage(session, parcel_number, result, meta)
            count += 1
        else:
            await session.execute(_DELETE_ASSEMBLAGE_SQL, {"parcel_number": parcel_number})
    return count


_TOP_SELECT = (
    "SELECT pa.parcel_number, p.address, pa.potential, pa.candidate_count, "
    "pa.combined_lot_area_sqft, pa.by_right_units_current, pa.by_right_units_combined, "
    "pa.unit_unlock, pa.base_zoning_code, pa.neighborhood "
    "FROM parcel_assemblage pa JOIN parcel p ON p.parcel_number = pa.parcel_number"
)


async def top_plays(
    session: AsyncSession,
    *,
    neighborhood: str | None = None,
    zoning: str | None = None,
    limit: int = 100,
) -> AssemblageTopResponse:
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if neighborhood is not None:
        conditions.append("pa.neighborhood ILIKE :neighborhood")
        params["neighborhood"] = neighborhood
    if zoning is not None:
        conditions.append("pa.base_zoning_code ILIKE :zoning || '%'")
        params["zoning"] = zoning
    where = " AND ".join(conditions) if conditions else "TRUE"

    total = await session.scalar(
        text(f"SELECT count(*) FROM parcel_assemblage pa WHERE {where}"), params
    )
    rows = (
        await session.execute(
            text(
                f"{_TOP_SELECT} WHERE {where} "
                "ORDER BY pa.unit_unlock DESC NULLS LAST, "
                "pa.combined_lot_area_sqft DESC NULLS LAST, pa.parcel_number "
                "LIMIT :limit"
            ),
            params,
        )
    ).all()
    plays = [
        AssemblageTopPlay(
            parcel_number=row.parcel_number,
            address=row.address,
            potential=row.potential,
            candidate_count=row.candidate_count,
            combined_lot_area_sqft=_as_float(row.combined_lot_area_sqft),
            by_right_units_current=row.by_right_units_current,
            by_right_units_combined=row.by_right_units_combined,
            unit_unlock=row.unit_unlock,
            base_zoning_code=row.base_zoning_code,
            neighborhood=row.neighborhood,
        )
        for row in rows
    ]
    return AssemblageTopResponse(total=int(total or 0), returned=len(plays), plays=plays)
