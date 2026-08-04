from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator

from lotscope.core.provenance import FieldProvenance
from lotscope.valuation.confidence import (
    ValueConfidence,
    value_confidence_band,
    value_support_note,
)


def _no_trust_when_absent(value: object) -> object:
    return {} if value is None else value


FieldTrust = Annotated[dict[str, FieldProvenance], BeforeValidator(_no_trust_when_absent)]


class VerdictResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parcel_number: str
    verdict_version: str
    buildability_score: float | None
    opportunity_score: float
    summary: str
    can_build_by_right: bool | None
    by_right_units: int | None
    max_height_ft: float | None
    needs_variance: bool | None
    buildable_area_sqft: float | None
    value_estimate_low: float | None
    value_estimate_high: float | None
    value_confidence: float | None
    assessment_market_gap: float | None
    arv: float | None
    est_profit: float | None
    est_margin: float | None
    max_allowable_offer: float | None
    deal_score: float | None
    is_underpriced: bool | None
    risk_score: float | None
    risk_flags: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    field_trust: FieldTrust = {}
    recommendation: str | None = None
    recommendation_reason: str | None = None
    decision_version: str | None = None
    computed_at: datetime
    value_confidence_band: ValueConfidence | None = None
    value_support_note: str = ""

    @model_validator(mode="after")
    def _derive_value_support(self) -> "VerdictResult":
        priced = self.value_estimate_low is not None and self.value_estimate_high is not None
        band = value_confidence_band(self.value_confidence) if priced else None
        self.value_confidence_band = band
        self.value_support_note = value_support_note(band if priced else None)
        return self
