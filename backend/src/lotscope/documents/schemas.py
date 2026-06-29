from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

RestrictionKind = Literal["use_restriction", "easement", "covenant", "condition", "access", "other"]
Confidence = Literal["high", "medium", "low"]


class ExtractedRestriction(BaseModel):
    kind: RestrictionKind = Field(
        description="The category of the restriction found in the deed text."
    )
    text: str = Field(
        description="A short plain-English statement of the restriction, grounded in the deed text."
    )
    citation: str | None = Field(
        default=None,
        description=(
            "The clause, paragraph, or quoted phrase in the deed the restriction comes from."
        ),
    )
    confidence: Confidence = Field(
        description="Confidence that this is a real, currently-binding restriction."
    )


class DeedExtraction(BaseModel):
    has_restrictions: bool = Field(
        description=(
            "True only if the deed text contains explicit restrictions, easements, or covenants."
        )
    )
    restrictions: list[ExtractedRestriction] = Field(
        default_factory=list,
        description="Every restriction, easement, covenant, or condition found; empty if none.",
    )


class DeedRestrictionItem(BaseModel):
    kind: str
    text: str
    citation: str | None
    confidence: str
    document_type: str | None
    recording_date: date | None


class DeedRestrictionsResponse(BaseModel):
    parcel_number: str
    count: int
    restrictions: list[DeedRestrictionItem]
