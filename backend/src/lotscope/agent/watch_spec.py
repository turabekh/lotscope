"""A standing description of the lots a buyer wants to hear about.

A watch is either one parcel or a spec: an area plus the filters that decide whether a new
listing in it is worth their attention. The spec is the shape saved searches used to hold,
so a saved search migrates into a watch without losing what it asked for.

The spec is stored on an agent_alert of kind "new_match", which is what the nightly signal
builder reads. It deliberately holds no results: a watch is a question, and the answer is
whatever the sources say tonight.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_ZONING_CODES = 40


class WatchSpec(BaseModel):
    """The filters a watched search applies to a new listing."""

    name: str = Field(default="Watched search", max_length=120)
    zip_codes: list[str] = Field(default_factory=list, max_length=40)
    zoning_codes: list[str] = Field(default_factory=list, max_length=MAX_ZONING_CODES)
    vacant_only: bool = True
    exclude_city_owned: bool = True
    min_lot_area_sqft: float | None = Field(default=None, ge=0)
    max_lot_area_sqft: float | None = Field(default=None, ge=0)
    min_market_value: float | None = Field(default=None, ge=0)
    max_market_value: float | None = Field(default=None, ge=0)
    is_delinquent: bool | None = None

    @field_validator("zoning_codes", "zip_codes")
    @classmethod
    def _tidy(cls, values: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for value in values:
            cleaned = value.strip().upper()
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)

    def describe(self) -> str:
        parts: list[str] = []
        if self.vacant_only:
            parts.append("vacant lots")
        else:
            parts.append("lots")
        if self.zoning_codes:
            parts.append(f"zoned {', '.join(self.zoning_codes)}")
        if self.zip_codes:
            parts.append(f"in {', '.join(self.zip_codes)}")
        if self.min_lot_area_sqft:
            parts.append(f"at least {self.min_lot_area_sqft:,.0f} sqft")
        if self.exclude_city_owned:
            parts.append("excluding city-owned")
        return " ".join(parts)


def from_saved_search(name: str, criteria: dict[str, Any]) -> WatchSpec:
    """Carry a saved search's criteria across without inventing anything it did not say."""
    zip_code = criteria.get("zip_code")
    return WatchSpec(
        name=name[:120] or "Watched search",
        zip_codes=[zip_code] if zip_code else [],
        zoning_codes=list(criteria.get("zoning_codes") or []),
        vacant_only=bool(criteria.get("vacant_only", False)),
        exclude_city_owned=bool(criteria.get("exclude_city_owned", True)),
        min_lot_area_sqft=criteria.get("min_lot_area_sqft"),
        max_lot_area_sqft=criteria.get("max_lot_area_sqft"),
        min_market_value=criteria.get("min_market_value"),
        max_market_value=criteria.get("max_market_value"),
        is_delinquent=criteria.get("is_delinquent"),
    )


def spec_conditions(spec: WatchSpec, alias: str = "p") -> tuple[list[str], dict[str, Any]]:
    """SQL fragments for one spec. Shared by the buy box and by watched searches."""
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if spec.vacant_only:
        conditions.append(f"{alias}.is_vacant IS TRUE")
    if spec.exclude_city_owned:
        conditions.append(f"coalesce({alias}.is_city_owned, false) IS FALSE")
    if spec.zip_codes:
        conditions.append(f"left({alias}.zip_code, 5) = ANY(:spec_zips)")
        params["spec_zips"] = spec.zip_codes
    if spec.zoning_codes:
        conditions.append(
            f"upper(replace(coalesce({alias}.base_zoning_code, ''), '-', '')) = ANY(:spec_zoning)"
        )
        # RSA-5 and RSA5 are the same district written two ways, and the saved searches
        # on production contain both spellings.
        params["spec_zoning"] = [code.replace("-", "") for code in spec.zoning_codes]
    if spec.min_lot_area_sqft is not None:
        conditions.append(f"{alias}.lot_area_sqft >= :spec_min_lot")
        params["spec_min_lot"] = spec.min_lot_area_sqft
    if spec.max_lot_area_sqft is not None:
        conditions.append(f"{alias}.lot_area_sqft <= :spec_max_lot")
        params["spec_max_lot"] = spec.max_lot_area_sqft
    if spec.min_market_value is not None:
        conditions.append(f"{alias}.market_value >= :spec_min_value")
        params["spec_min_value"] = spec.min_market_value
    if spec.max_market_value is not None:
        conditions.append(f"{alias}.market_value <= :spec_max_value")
        params["spec_max_value"] = spec.max_market_value

    return conditions or ["TRUE"], params
