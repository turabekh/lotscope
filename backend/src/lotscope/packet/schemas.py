from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from lotscope.buybox.schemas import TargetUse

LotVerdict = Literal["BID", "LOOK", "PASS"]

OPENING_BID_NOTE = (
    "The published opening bid is a minimum, nominal on tax sales — expect to compete. "
    "It does not price the lot and nothing in this packet is graded on it."
)

VERIFY_BEFORE_BIDDING: tuple[str, ...] = (
    OPENING_BID_NOTE,
    "Water and sewer liens — the Water Revenue Bureau does not publish them per parcel and we "
    "do not hold them. A vacant lot can carry years of unbilled service charges.",
    "Gas liens and PGW balances — not in any dataset we ingest.",
    "Other municipal liens and judgments not in the tax delinquency file.",
    "The upset price and any changes announced on the sale day itself.",
    "Physical condition, encroachments and access, which need an in-person look.",
    "Title — the deed chain, easements and restrictions beyond what we record.",
)


class SourceRef(BaseModel):
    source: str
    source_url: str
    fetched_at: datetime | None = None


class DataAsOf(BaseModel):
    source: str
    source_url: str
    fetched_at: datetime | None = None
    data_vintage: date | None = None


class RedFlag(BaseModel):
    code: str
    label: str
    detail: str
    severity: Literal["high", "medium", "low"]
    source: str
    source_url: str
    fetched_at: datetime | None = None


class AdjacentParcel(BaseModel):
    parcel_number: str
    address: str | None = None
    owner_class: Literal["public", "vacant", "owned_by_you", "other"]
    shared_boundary_ft: float | None = None
    lot_area_sqft: float | None = None


class PacketComp(BaseModel):
    parcel_number: str
    address: str | None = None
    sale_date: date | None = None
    sale_price: float | None = None
    distance_ft: float | None = None
    reason: str
    source: str
    source_url: str


class SensitiveInput(BaseModel):
    name: str
    detail: str
    swing: float


class LiveCheck(BaseModel):
    """One fact read from the primary source while the packet was being built.

    A packet is read at an auction, hours or days after the nightly ingest. For the lots a
    buyer might actually bid on, the two facts that move — open violations and whether the
    sale is still on — are re-read from the source and both timestamps are kept, so the
    reader can see how old each number is rather than assuming they are the same age.
    """

    field: Literal["open_violations", "sale_status"]
    stored: str | None = None
    live: str | None = None
    agrees: bool
    note: str
    source: str
    source_url: str | None = None
    ingested_at: datetime | None = None
    fetched_at: datetime | None = None
    correction_id: int | None = None


class PacketLot(BaseModel):
    parcel_number: str
    address: str | None = None
    case_number: str | None = None
    sale_type: str | None = None
    opening_bid: float | None = None
    opening_bid_note: str = OPENING_BID_NOTE
    status: str | None = None
    is_scheduled: bool
    plaintiff: str | None = None

    is_vacant: bool
    lot_area_sqft: float | None = None
    zoning_code: str | None = None
    overlays: list[str] = Field(default_factory=list)

    can_build_by_right: bool | None = None
    by_right_units: int | None = None
    dimensional_reason: str | None = None
    provision_id: str | None = None

    max_allowable_offer: float | None = None
    est_margin: float | None = None
    sensitive_inputs: list[SensitiveInput] = Field(default_factory=list)

    red_flags: list[RedFlag] = Field(default_factory=list)
    comps: list[PacketComp] = Field(default_factory=list)
    comp_range_low: float | None = None
    comp_range_high: float | None = None

    clearing_estimate: float | None = None
    clearing_sample_size: int = 0
    clearing_low: float | None = None
    clearing_high: float | None = None
    clearing_sufficient: bool = False
    clearing_reason: str | None = None
    clearing_source: str | None = None
    clearing_source_url: str | None = None

    adjacent: list[AdjacentParcel] = Field(default_factory=list)
    variance_needed: str | None = None
    variance_outlook: str | None = None

    verdict: LotVerdict
    verdict_reason: str
    graded_as: TargetUse
    grade_rule: str
    also: list[str] = Field(default_factory=list)
    computed_at: datetime
    verify_before_bidding: list[str] = Field(default_factory=list)
    live_checks: list[LiveCheck] = Field(default_factory=list)


class PassedLot(BaseModel):
    parcel_number: str
    address: str | None = None
    reason: str
    grade_rule: str | None = None


class PacketHeader(BaseModel):
    sale_date: date
    target_use: TargetUse
    computed_at: datetime
    sale_types: list[str]
    listings: int
    vacant: int
    passing_buy_box: int
    generated_at: datetime
    data_as_of: list[DataAsOf]


class PacketModel(BaseModel):
    header: PacketHeader
    lots: list[PacketLot]
    passed: list[PassedLot]
    non_vacant_appendix: list[PassedLot]
    buy_box_summary: dict[str, object]
    verify_before_bidding: list[str] = Field(default_factory=lambda: list(VERIFY_BEFORE_BIDDING))
