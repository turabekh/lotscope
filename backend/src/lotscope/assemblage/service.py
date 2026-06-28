from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
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
from lotscope.assemblage.schemas import (
    AdjacentLot,
    AssemblageResult,
    AssemblageSummary,
    Potential,
)
from lotscope.zoning.service import assemblage_unit_estimate

_ADJACENCY_TOLERANCE_FT = 2.0
_NEIGHBOR_LIMIT = 16

_TARGET_SQL = text(
    "SELECT owner, base_zoning_code, lot_area_sqft, frontage_ft, "
    "(geom_2272 IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_NEIGHBORS_SQL = text(
    "WITH t AS ("
    "  SELECT owner, base_zoning_code, geom_2272 FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT n.parcel_number, n.address, n.owner, n.base_zoning_code, n.lot_area_sqft, "
    "n.frontage_ft, n.market_value, n.is_vacant, n.is_city_owned, "
    "(n.owner IS NOT NULL AND t.owner IS NOT NULL "
    " AND lower(btrim(n.owner)) = lower(btrim(t.owner))) AS same_owner, "
    "(n.base_zoning_code IS NOT NULL AND t.base_zoning_code IS NOT NULL "
    " AND upper(replace(n.base_zoning_code, '-', '')) = upper(replace(t.base_zoning_code, '-', ''))"
    ") AS same_zoning, "
    "ST_Length(ST_CollectionExtract(ST_Intersection(n.geom_2272, t.geom_2272), 2)) "
    "AS shared_boundary_ft "
    "FROM t JOIN parcel n ON n.parcel_number <> :parcel_number AND n.geom_2272 IS NOT NULL "
    "AND ST_DWithin(n.geom_2272, t.geom_2272, :tolerance) "
    "ORDER BY same_owner DESC, n.is_vacant DESC NULLS LAST, shared_boundary_ft DESC NULLS LAST "
    "LIMIT :limit"
)

_SOURCES: list[dict[str, Any]] = [
    {"source": "pwd_parcel", "field": "geom_2272"},
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
