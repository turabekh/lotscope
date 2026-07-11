from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buyers.derivation import (
    BUYER_MIN_LOT_PURCHASES,
    BUYER_MIN_PRICE,
    BUYER_WINDOW_MONTHS,
    BuyerSaleRow,
    DerivedBuyer,
    derive_buyers,
)
from lotscope.buyers.schemas import (
    BuyerProfileDetail,
    BuyerPurchase,
    BuyerRoster,
    BuyersNearby,
    BuyerStats,
    NearbyBuyer,
)
from lotscope.core.sql import normalized_name_sql, package_deed_exclusion_sql
from lotscope.ingestion.service import record_freshness

BUYER_DATASET = "buyer_profile"
BUYER_NEAR_RADIUS_FT = 2640.0

_CANDIDATE_SQL = text(
    "WITH candidate AS ("
    "  SELECT s.grantor AS grantor, s.grantee AS grantee, s.parcel_number AS parcel_number, "
    "         s.sale_price AS sale_price, s.sale_date AS sale_date, p.is_vacant AS is_vacant, "
    "         ST_X(ST_Centroid(p.geom_local)) AS cx, ST_Y(ST_Centroid(p.geom_local)) AS cy, "
    "         ST_SRID(p.geom_local) AS srid, "
    f"        {normalized_name_sql('s.grantee')} AS bkey "
    "  FROM sale s JOIN parcel p ON p.parcel_number = s.parcel_number "
    "  WHERE p.market_code = :market "
    "    AND s.sale_price >= :min_price "
    "    AND s.sale_date >= :since "
    "    AND s.grantee IS NOT NULL AND btrim(s.grantee) <> '' "
    f"   AND {package_deed_exclusion_sql('s')} "
    "), qualified AS ("
    "  SELECT bkey FROM candidate WHERE is_vacant IS TRUE AND bkey IS NOT NULL "
    "  GROUP BY bkey HAVING count(*) >= :min_lot"
    ") "
    "SELECT c.grantor, c.grantee, c.parcel_number, c.sale_price, c.sale_date, "
    "       c.is_vacant, c.cx, c.cy, c.srid "
    "FROM candidate c JOIN qualified q ON q.bkey = c.bkey"
)

_MAILING_SQL = text(
    "SELECT DISTINCT ON (owner_key) owner_key, mailing_address "
    "FROM parcel "
    "WHERE market_code = :market AND owner_key = ANY(:keys) AND mailing_address IS NOT NULL "
    "ORDER BY owner_key"
)

_UPSERT_SQL = text(
    "INSERT INTO buyer_profile "
    "(market_code, buyer_key, display_name, purchases_window, lot_purchases_window, "
    " last_purchase_at, median_price, total_consideration, mailing_address, activity_centroid, "
    " computed_at, source) "
    "VALUES (:market, :buyer_key, :display_name, :purchases_window, :lot_purchases_window, "
    " :last_purchase_at, :median_price, :total_consideration, :mailing_address, "
    " ST_SetSRID("
    "   ST_MakePoint(CAST(:cx AS double precision), CAST(:cy AS double precision)), "
    "   COALESCE(CAST(:srid AS integer), 0)), "
    " :computed_at, :source) "
    "ON CONFLICT (market_code, buyer_key) DO UPDATE SET "
    " display_name = EXCLUDED.display_name, "
    " purchases_window = EXCLUDED.purchases_window, "
    " lot_purchases_window = EXCLUDED.lot_purchases_window, "
    " last_purchase_at = EXCLUDED.last_purchase_at, "
    " median_price = EXCLUDED.median_price, "
    " total_consideration = EXCLUDED.total_consideration, "
    " mailing_address = EXCLUDED.mailing_address, "
    " activity_centroid = EXCLUDED.activity_centroid, "
    " computed_at = EXCLUDED.computed_at, "
    " source = EXCLUDED.source"
)

_REVOKE_SQL = text(
    "DELETE FROM buyer_profile WHERE market_code = :market AND NOT (buyer_key = ANY(:keys))"
)

_REVOKE_ALL_SQL = text("DELETE FROM buyer_profile WHERE market_code = :market")

_NEARBY_SQL = text(
    "WITH subject AS ("
    "  SELECT ST_Centroid(geom_local) AS pt, market_code "
    "  FROM parcel WHERE parcel_number = :parcel_number"
    ") "
    "SELECT bp.buyer_key, bp.display_name, bp.purchases_window, bp.lot_purchases_window, "
    "       bp.last_purchase_at, bp.median_price, bp.total_consideration, bp.mailing_address, "
    "       ST_Distance(subject.pt, bp.activity_centroid) AS distance_ft "
    "FROM buyer_profile bp CROSS JOIN subject "
    "WHERE bp.market_code = subject.market_code "
    "  AND bp.activity_centroid IS NOT NULL "
    "  AND ST_DWithin(bp.activity_centroid, subject.pt, :radius_ft) "
    "ORDER BY distance_ft, bp.last_purchase_at DESC NULLS LAST "
    "LIMIT :limit"
)

_ROSTER_SQL = text(
    "SELECT buyer_key, display_name, purchases_window, lot_purchases_window, "
    "       last_purchase_at, median_price, total_consideration, mailing_address "
    "FROM buyer_profile "
    "WHERE market_code = :market AND lot_purchases_window >= :min_purchases "
    "ORDER BY lot_purchases_window DESC, last_purchase_at DESC NULLS LAST, buyer_key "
    "LIMIT :limit OFFSET :offset"
)

_ROSTER_COUNT_SQL = text(
    "SELECT count(*) FROM buyer_profile "
    "WHERE market_code = :market AND lot_purchases_window >= :min_purchases"
)

_PROFILE_SQL = text(
    "SELECT buyer_key, display_name, purchases_window, lot_purchases_window, "
    "       last_purchase_at, median_price, total_consideration, mailing_address, computed_at "
    "FROM buyer_profile WHERE market_code = :market AND buyer_key = :buyer_key"
)

_PURCHASES_SQL = text(
    "SELECT s.parcel_number, p.address, s.sale_date, s.sale_price, p.is_vacant "
    f"FROM sale s JOIN parcel p ON p.parcel_number = s.parcel_number "
    "WHERE p.market_code = :market "
    f"  AND {normalized_name_sql('s.grantee')} = :buyer_key "
    "  AND s.sale_price >= :min_price "
    "  AND s.sale_date >= :since "
    f"  AND {package_deed_exclusion_sql('s')} "
    "ORDER BY s.sale_date DESC NULLS LAST "
    "LIMIT :limit"
)


_PARCEL_MARKET_SQL = text("SELECT market_code FROM parcel WHERE parcel_number = :parcel_number")


def _f(value: Any) -> float | None:
    return float(value) if value is not None else None


async def parcel_market(session: AsyncSession, parcel_number: str) -> str | None:
    return cast(
        "str | None", await session.scalar(_PARCEL_MARKET_SQL, {"parcel_number": parcel_number})
    )


def _window_start(now: datetime) -> date:
    year = now.year - (BUYER_WINDOW_MONTHS // 12)
    return date(year, now.month, 1)


async def recompute_buyer_profiles(
    session: AsyncSession, *, market_code: str = "phl", now: datetime | None = None
) -> int:
    stamp = now or datetime.now(UTC)
    since = _window_start(stamp)
    rows = await session.execute(
        _CANDIDATE_SQL,
        {
            "market": market_code,
            "min_price": BUYER_MIN_PRICE,
            "since": since,
            "min_lot": BUYER_MIN_LOT_PURCHASES,
        },
    )
    sale_rows = [
        BuyerSaleRow(
            grantor=r.grantor,
            grantee=r.grantee,
            parcel_number=r.parcel_number,
            sale_price=float(r.sale_price),
            sale_date=r.sale_date,
            is_vacant=bool(r.is_vacant),
            centroid_x=_f(r.cx),
            centroid_y=_f(r.cy),
            srid=int(r.srid) if r.srid is not None else None,
        )
        for r in rows
    ]
    profiles = derive_buyers(sale_rows)
    keys = [p.buyer_key for p in profiles]

    mailing: dict[str, str] = {}
    if keys:
        mail_rows = await session.execute(_MAILING_SQL, {"market": market_code, "keys": keys})
        mailing = {row.owner_key: row.mailing_address for row in mail_rows}

    for profile in profiles:
        await session.execute(
            _UPSERT_SQL, _upsert_params(profile, market_code, mailing.get(profile.buyer_key), stamp)
        )

    if keys:
        await session.execute(_REVOKE_SQL, {"market": market_code, "keys": keys})
    else:
        await session.execute(_REVOKE_ALL_SQL, {"market": market_code})

    await record_freshness(
        session,
        BUYER_DATASET,
        market_code=market_code,
        status="success",
        success=True,
        row_count=len(profiles),
    )
    return len(profiles)


def _upsert_params(
    profile: DerivedBuyer, market_code: str, mailing_address: str | None, stamp: datetime
) -> dict[str, Any]:
    return {
        "market": market_code,
        "buyer_key": profile.buyer_key,
        "display_name": profile.display_name,
        "purchases_window": profile.purchases_window,
        "lot_purchases_window": profile.lot_purchases_window,
        "last_purchase_at": profile.last_purchase_at,
        "median_price": profile.median_price,
        "total_consideration": profile.total_consideration,
        "mailing_address": mailing_address,
        "cx": profile.centroid_x,
        "cy": profile.centroid_y,
        "srid": profile.srid,
        "computed_at": stamp,
        "source": BUYER_DATASET,
    }


def _stats(row: Any) -> dict[str, Any]:
    return {
        "buyer_key": row.buyer_key,
        "display_name": row.display_name,
        "purchases_window": row.purchases_window,
        "lot_purchases_window": row.lot_purchases_window,
        "last_purchase_at": row.last_purchase_at,
        "median_price": _f(row.median_price),
        "total_consideration": _f(row.total_consideration),
        "mailing_address": row.mailing_address,
    }


async def buyers_near_parcel(
    session: AsyncSession,
    parcel_number: str,
    market_code: str,
    *,
    radius_ft: float = BUYER_NEAR_RADIUS_FT,
    limit: int = 25,
    computed_at: datetime | None = None,
) -> BuyersNearby:
    rows = await session.execute(
        _NEARBY_SQL,
        {"parcel_number": parcel_number, "radius_ft": radius_ft, "limit": limit},
    )
    buyers = [NearbyBuyer(**_stats(row), distance_ft=float(row.distance_ft)) for row in rows]
    return BuyersNearby(
        market_code=market_code,
        available=True,
        radius_ft=radius_ft,
        computed_at=computed_at,
        buyers=buyers,
    )


async def list_buyers(
    session: AsyncSession,
    market_code: str,
    *,
    min_purchases: int = BUYER_MIN_LOT_PURCHASES,
    limit: int = 50,
    offset: int = 0,
) -> BuyerRoster:
    total = await session.scalar(
        _ROSTER_COUNT_SQL, {"market": market_code, "min_purchases": min_purchases}
    )
    rows = await session.execute(
        _ROSTER_SQL,
        {"market": market_code, "min_purchases": min_purchases, "limit": limit, "offset": offset},
    )
    buyers = [BuyerStats(**_stats(row)) for row in rows]
    return BuyerRoster(
        market_code=market_code,
        available=True,
        total=int(total or 0),
        returned=len(buyers),
        buyers=buyers,
    )


async def get_buyer(
    session: AsyncSession, market_code: str, buyer_key: str, *, purchase_limit: int = 100
) -> BuyerProfileDetail | None:
    row = (
        await session.execute(_PROFILE_SQL, {"market": market_code, "buyer_key": buyer_key})
    ).first()
    if row is None:
        return None
    purchase_rows = await session.execute(
        _PURCHASES_SQL,
        {
            "market": market_code,
            "buyer_key": buyer_key,
            "min_price": BUYER_MIN_PRICE,
            "since": _window_start(datetime.now(UTC)),
            "limit": purchase_limit,
        },
    )
    purchases = [
        BuyerPurchase(
            parcel_number=pr.parcel_number,
            address=pr.address,
            sale_date=pr.sale_date,
            sale_price=_f(pr.sale_price),
            is_vacant=pr.is_vacant,
        )
        for pr in purchase_rows
    ]
    return BuyerProfileDetail(
        market_code=market_code,
        computed_at=row.computed_at,
        purchases=purchases,
        **_stats(row),
    )
