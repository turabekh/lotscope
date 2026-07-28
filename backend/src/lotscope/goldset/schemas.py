from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "material", "minor"]
ReviewStatus = Literal["unreviewed", "reviewed", "disputed"]

GoldCategory = Literal[
    "standard_rsa_rowhouse",
    "undersized_lot",
    "oversized_or_double_lot",
    "corner_or_irregular",
    "assemblage_candidate",
    "mixed_use_district",
    "multifamily_district",
    "industrial",
    "special_purpose_district",
    "historic",
    "flood_exposure",
    "public_ownership",
    "tax_delinquency",
    "access_problem",
    "developed_appearing_vacant",
    "known_permit",
    "zoning_appeal",
]

CRITICAL_FIELDS: frozenset[str] = frozenset(
    {
        "district_code",
        "can_build_by_right",
        "by_right_units",
        "requires_master_plan",
        "street_access",
    }
)


class ExpectedFacts(BaseModel):
    district_code: str | None = None
    can_build_by_right: bool | None = None
    by_right_units: int | None = None
    requires_master_plan: bool | None = None
    street_access: bool | None = None
    expected_risk_flags: list[str] = Field(default_factory=list)


class GoldCase(BaseModel):
    parcel_number: str
    categories: list[GoldCategory] = Field(min_length=1)
    expected: ExpectedFacts
    evidence_refs: list[str] = Field(default_factory=list)
    reviewer: str | None = None
    reviewed_on: date | None = None
    review_status: ReviewStatus = "unreviewed"
    notes: str | None = None

    def model_post_init(self, __context: object) -> None:
        if self.review_status == "reviewed" and not (self.reviewer or "").strip():
            raise ValueError(
                "A case cannot be marked reviewed without a named reviewer; professional review "
                "is recorded by a person, never inferred."
            )
        if self.review_status == "reviewed" and self.reviewed_on is None:
            raise ValueError("A reviewed case must record the date it was reviewed.")


class Discrepancy(BaseModel):
    parcel_number: str
    field_name: str
    expected: str | None
    actual: str | None
    severity: Severity


class EvaluationReport(BaseModel):
    verdict_version: str
    total_cases: int
    evaluated: int
    missing_verdict: list[str] = Field(default_factory=list)
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    reviewed_cases: int = 0
    category_coverage: dict[str, int] = Field(default_factory=dict)

    @property
    def critical(self) -> int:
        return sum(1 for d in self.discrepancies if d.severity == "critical")

    @property
    def material(self) -> int:
        return sum(1 for d in self.discrepancies if d.severity == "material")

    @property
    def minor(self) -> int:
        return sum(1 for d in self.discrepancies if d.severity == "minor")
