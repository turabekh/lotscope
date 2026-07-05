from collections.abc import Mapping
from datetime import UTC, date, datetime

from sqlalchemy import TextClause, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zba.schemas import VarianceOutlook

_WINDOW_YEARS = 3

_GRANTED_DECISIONS = frozenset({"GRANTED", "GRANTED/PROV"})
_DENIED_DECISIONS = frozenset({"DENIED", "DENIED/PROV"})
_DECIDED_DECISIONS = _GRANTED_DECISIONS | _DENIED_DECISIONS

_WINDOW_MONTHS = 36
_MIN_DECIDED = 10
_MIN_LOCAL_DECIDED = 30

_SUBJECT_SQL = text(
    "SELECT base_zoning_code, zip_code FROM parcel WHERE parcel_number = :parcel_number"
)
_DISTRICT_COUNTS_SQL = text(
    "SELECT z.decision AS decision, count(*) AS n "
    "FROM zba_appeal z JOIN parcel p ON p.parcel_number = z.parcel_number "
    "WHERE p.base_zoning_code = :district AND z.decision_date >= :cutoff "
    "GROUP BY z.decision"
)
_ZIP_COUNTS_SQL = text(
    "SELECT z.decision AS decision, count(*) AS n "
    "FROM zba_appeal z JOIN parcel p ON p.parcel_number = z.parcel_number "
    "WHERE p.base_zoning_code = :district AND p.zip_code = :zip_code "
    "AND z.decision_date >= :cutoff "
    "GROUP BY z.decision"
)

_SOURCES = [{"source": "appeals", "signal": "zba_variance_outlook"}]


def summarize_decisions(decision_counts: Mapping[str, int]) -> tuple[int, int]:
    granted = sum(n for decision, n in decision_counts.items() if decision in _GRANTED_DECISIONS)
    decided = sum(n for decision, n in decision_counts.items() if decision in _DECIDED_DECISIONS)
    return granted, decided


def _rate(granted: int, decided: int) -> float | None:
    return round(granted / decided, 3) if decided else None


def _window_start(reference: date) -> date:
    try:
        return reference.replace(year=reference.year - _WINDOW_YEARS)
    except ValueError:
        return reference.replace(year=reference.year - _WINDOW_YEARS, day=28)


async def _decision_counts(
    session: AsyncSession, statement: TextClause, params: dict[str, object]
) -> dict[str, int]:
    rows = await session.execute(statement, params)
    return {row.decision: row.n for row in rows if row.decision is not None}


async def variance_outlook(
    session: AsyncSession, parcel_number: str, *, today: date | None = None
) -> VarianceOutlook | None:
    subject = (await session.execute(_SUBJECT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        return None

    computed_at = datetime.now(UTC)
    reference = today if today is not None else datetime.now(UTC).date()
    cutoff = _window_start(reference)
    district = subject.base_zoning_code

    def _empty(reason: str) -> VarianceOutlook:
        return VarianceOutlook(
            parcel_number=parcel_number,
            district=district,
            population_label=f"all ZBA appeals for {district or 'unknown'} parcels",
            window_months=_WINDOW_MONTHS,
            decided=0,
            granted=0,
            grant_rate=None,
            local_scope=None,
            local_decided=None,
            local_grant_rate=None,
            reason=reason,
            sources=_SOURCES,
            computed_at=computed_at,
        )

    if not district:
        return _empty("Zoning district is unknown, so no comparable ZBA population exists.")

    counts = await _decision_counts(
        session, _DISTRICT_COUNTS_SQL, {"district": district, "cutoff": cutoff}
    )
    granted, decided = summarize_decisions(counts)
    if decided < _MIN_DECIDED:
        return VarianceOutlook(
            parcel_number=parcel_number,
            district=district,
            population_label=f"all ZBA appeals for {district} parcels",
            window_months=_WINDOW_MONTHS,
            decided=decided,
            granted=granted,
            grant_rate=None,
            local_scope=None,
            local_decided=None,
            local_grant_rate=None,
            reason=(
                f"Only {decided} decided ZBA appeal(s) for {district} parcels in the last "
                f"{_WINDOW_MONTHS} months — too few to estimate a grant rate."
            ),
            sources=_SOURCES,
            computed_at=computed_at,
        )

    local_scope: str | None = None
    local_decided: int | None = None
    local_grant_rate: float | None = None
    if subject.zip_code:
        zip_counts = await _decision_counts(
            session,
            _ZIP_COUNTS_SQL,
            {"district": district, "zip_code": subject.zip_code, "cutoff": cutoff},
        )
        zip_granted, zip_decided = summarize_decisions(zip_counts)
        if zip_decided >= _MIN_LOCAL_DECIDED:
            local_scope = f"ZIP {subject.zip_code}"
            local_decided = zip_decided
            local_grant_rate = _rate(zip_granted, zip_decided)

    return VarianceOutlook(
        parcel_number=parcel_number,
        district=district,
        population_label=f"all ZBA appeals for {district} parcels",
        window_months=_WINDOW_MONTHS,
        decided=decided,
        granted=granted,
        grant_rate=_rate(granted, decided),
        local_scope=local_scope,
        local_decided=local_decided,
        local_grant_rate=local_grant_rate,
        reason=None,
        sources=_SOURCES,
        computed_at=computed_at,
    )
