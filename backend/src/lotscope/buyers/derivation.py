from dataclasses import dataclass
from datetime import date
from statistics import fmean, median

from lotscope.core.names import is_related_party, normalize_party_key

BUYER_WINDOW_MONTHS = 24
BUYER_MIN_LOT_PURCHASES = 3
BUYER_MIN_PRICE = 1000.0

_GOVERNMENT_BUYER_TOKENS = (
    "LAND BANK",
    "REDEVELOPMENT AUTHORITY",
    "PHILADELPHIA REDEVELOPMENT",
    "PHDC",
    "HOUSING AUTHORITY",
    "CITY OF PHILADELPHIA",
    "COMMONWEALTH OF PENNSYLVANIA",
    "SCHOOL DISTRICT",
    "COUNTY OF",
    "COMMONWEALTH OF",
    "UNITED STATES OF AMERICA",
)


def is_government_buyer(name: str | None) -> bool:
    key = normalize_party_key(name)
    if key is None:
        return False
    return any(token in key for token in _GOVERNMENT_BUYER_TOKENS)


@dataclass(frozen=True)
class BuyerSaleRow:
    grantor: str | None
    grantee: str | None
    parcel_number: str
    sale_price: float
    sale_date: date
    is_vacant: bool
    centroid_x: float | None
    centroid_y: float | None
    srid: int | None = None


@dataclass(frozen=True)
class DerivedBuyer:
    buyer_key: str
    display_name: str
    purchases_window: int
    lot_purchases_window: int
    last_purchase_at: date
    median_price: float
    total_consideration: float
    centroid_x: float | None
    centroid_y: float | None
    srid: int | None


def _arms_length(row: BuyerSaleRow) -> bool:
    if is_related_party(row.grantor, row.grantee):
        return False
    if is_government_buyer(row.grantee):
        return False
    return row.sale_price >= BUYER_MIN_PRICE


def derive_buyers(
    rows: list[BuyerSaleRow],
    *,
    min_lot_purchases: int = BUYER_MIN_LOT_PURCHASES,
) -> list[DerivedBuyer]:
    grouped: dict[str, list[BuyerSaleRow]] = {}
    latest_name: dict[str, tuple[date, str]] = {}
    for row in rows:
        if not _arms_length(row):
            continue
        key = normalize_party_key(row.grantee)
        if key is None:
            continue
        grouped.setdefault(key, []).append(row)
        display = row.grantee.strip() if row.grantee else key
        if key not in latest_name or row.sale_date >= latest_name[key][0]:
            latest_name[key] = (row.sale_date, display)

    profiles: list[DerivedBuyer] = []
    for key, buyer_rows in grouped.items():
        lot_rows = [r for r in buyer_rows if r.is_vacant]
        if len(lot_rows) < min_lot_purchases:
            continue
        lot_prices = [r.sale_price for r in lot_rows]
        located = [r for r in lot_rows if r.centroid_x is not None and r.centroid_y is not None]
        xs = [r.centroid_x for r in located if r.centroid_x is not None]
        ys = [r.centroid_y for r in located if r.centroid_y is not None]
        srid = next((r.srid for r in located if r.srid is not None), None)
        profiles.append(
            DerivedBuyer(
                buyer_key=key,
                display_name=latest_name[key][1],
                purchases_window=len(buyer_rows),
                lot_purchases_window=len(lot_rows),
                last_purchase_at=max(r.sale_date for r in lot_rows),
                median_price=float(median(lot_prices)),
                total_consideration=float(sum(r.sale_price for r in buyer_rows)),
                centroid_x=fmean(xs) if xs else None,
                centroid_y=fmean(ys) if ys else None,
                srid=srid,
            )
        )
    profiles.sort(key=lambda b: (-b.lot_purchases_window, b.buyer_key))
    return profiles
