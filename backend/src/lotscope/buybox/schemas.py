from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lotscope.deal.assumptions import CANONICAL_ASSUMPTION_KEYS

TargetUse = Literal["hold", "build", "flip", "assemble"]

MAX_AREAS = 20
MAX_ZONING_CODES = 30
MAX_OWNED_PARCELS = 500

DEFAULT_TARGET_USE: TargetUse = "build"
DEFAULT_MIN_LOT_SQFT = 640
DEFAULT_EXCLUDE_CITY_NEIGHBOR = False
DEFAULT_EXCLUDE_OPEN_VIOLATIONS = False
DEFAULT_EXCLUDE_HISTORIC = True
DEFAULT_EXCLUDE_FLOOD = True
DEFAULT_FLIP_BID_RATIO = 0.70


class BuyBoxArea(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    polygon: dict[str, object] | None = Field(
        default=None,
        description="A GeoJSON Polygon or MultiPolygon in EPSG:4326 bounding the area.",
    )
    zip_codes: list[str] = Field(
        default_factory=list,
        max_length=40,
        description="Philadelphia ZIP codes, used when no polygon is drawn.",
    )

    @field_validator("name")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("An area needs a name.")
        return cleaned


class BuyBoxWrite(BaseModel):
    areas: list[BuyBoxArea] = Field(
        default_factory=list,
        max_length=MAX_AREAS,
        description=(
            "Where the buyer will actually go. Empty means the whole city: a new buyer has not "
            "picked a hunting ground yet, and silently narrowing to one would hide lots."
        ),
    )
    max_bid: float | None = Field(
        default=None,
        ge=0,
        le=99_999_999.99,
        description=(
            "The most this buyer will pay at auction, before costs. Null by default because "
            "the ceiling is personal; the deal engine computes an MAO regardless."
        ),
    )
    target_use: TargetUse = Field(
        default=DEFAULT_TARGET_USE,
        description=(
            "Which lens grades a lot. build by default: the product is aimed at infill "
            "developers, and on a vacant Philadelphia lot holding or flipping earns nothing "
            "the zoning envelope does not. assemble grades on what an adjacent parcel unlocks; "
            "hold and flip grade the opening bid against the land comps instead."
        ),
    )
    min_lot_sqft: int | None = Field(
        default=DEFAULT_MIN_LOT_SQFT,
        ge=0,
        le=10_000_000,
        description=(
            "640 sqft is a 16x40 rowhouse lot — the smallest parcel RSA-5 will carry a "
            "by-right house on. Below it the buyer is bidding on a side yard."
        ),
    )
    zoning_codes: list[str] = Field(
        default_factory=list,
        max_length=MAX_ZONING_CODES,
        description=(
            "Empty by default, meaning every district. A code list is a filter a buyer adds "
            "once they know what they build; pre-filling it would silently drop RM and CMX lots."
        ),
    )
    exclude_city_neighbor: bool = Field(
        default=DEFAULT_EXCLUDE_CITY_NEIGHBOR,
        description=(
            "False by default: a Land Bank or PHDC neighbour is an assemblage opportunity as "
            "often as an obstacle, so it is surfaced rather than filtered."
        ),
    )
    exclude_open_violations: bool = Field(
        default=DEFAULT_EXCLUDE_OPEN_VIOLATIONS,
        description=(
            "False by default: open L&I violations on a vacant lot are usually cleanup, priced "
            "into the offer rather than disqualifying."
        ),
    )
    exclude_historic: bool = Field(
        default=DEFAULT_EXCLUDE_HISTORIC,
        description=(
            "True by default: a historic district adds Historical Commission review to every "
            "permit, which most buyers of a single lot are not staffed to carry."
        ),
    )
    exclude_flood: bool = Field(
        default=DEFAULT_EXCLUDE_FLOOD,
        description=(
            "True by default: an SFHA parcel needs flood insurance and elevated construction, "
            "and the cost lands after the auction when the price is already fixed."
        ),
    )
    flip_bid_ratio: float = Field(
        default=DEFAULT_FLIP_BID_RATIO,
        gt=0.0,
        le=1.0,
        description=(
            "For a hold or flip buyer, the fraction of the low comparable a bid must sit under "
            "to be worth taking. 0.70 by default: a resale buyer who is not building has only "
            "the spread to the next sale, and 30 percent is the room that carries transfer tax, "
            "holding costs and a soft market. It does not apply to the build lens, where the "
            "offer comes from the construction pro forma instead."
        ),
    )
    assumptions: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Deal assumptions that override the platform defaults, keyed by the names in "
            "deal/assumptions.py. Empty means the platform defaults apply unchanged."
        ),
    )
    owned_parcels: list[Annotated[str, Field(max_length=40)]] = Field(
        default_factory=list,
        max_length=MAX_OWNED_PARCELS,
        description=(
            "Parcels this buyer already owns, so adjacency and assemblage can be read from "
            "them. Seeded from the OPA owner name on request, then edited by hand."
        ),
    )

    @field_validator("assumptions")
    @classmethod
    def _validate_assumptions(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = sorted(set(value) - CANONICAL_ASSUMPTION_KEYS)
        if unknown:
            raise ValueError(
                f"Unknown deal assumptions: {', '.join(unknown)}. "
                f"Known names are {', '.join(sorted(CANONICAL_ASSUMPTION_KEYS))}."
            )
        for name, number in value.items():
            if number < 0:
                raise ValueError(f"{name} cannot be negative.")
            if name.endswith(("_pct", "_margin")) and not 0.0 <= number <= 1.0:
                raise ValueError(f"{name} must be a fraction in [0, 1], got {number!r}.")
        return value

    @field_validator("zoning_codes")
    @classmethod
    def _normalise_codes(cls, value: list[str]) -> list[str]:
        return [code.strip().upper() for code in value if code.strip()]

    @field_validator("owned_parcels")
    @classmethod
    def _normalise_parcels(cls, value: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for parcel in value:
            cleaned = parcel.strip().lower()
            if cleaned:
                seen[cleaned] = None
        return list(seen)


class BuyBoxRead(BuyBoxWrite):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    is_configured: bool = Field(
        description=(
            "False until the buyer saves a box of their own. The defaults are usable, so the "
            "difference is invisible in the numbers and has to be carried explicitly."
        )
    )
    created_at: datetime
    updated_at: datetime


class OwnedParcelSeed(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)


class OwnedParcelSeedResult(BaseModel):
    owner_name: str
    added: list[str]
    owned_parcels: list[str]
    source: str
    source_url: str
    fetched_at: datetime
