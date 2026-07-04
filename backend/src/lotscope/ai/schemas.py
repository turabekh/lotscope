from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RetrievedDocument(BaseModel):
    id: int
    source: str
    section: str | None
    title: str | None
    content: str
    distance: float


class Citation(BaseModel):
    source: str = Field(description="The dataset or document the fact came from, e.g. 'Title 14'.")
    section: str = Field(description="The specific section or identifier cited, e.g. '14-701'.")


class ParcelAnswer(BaseModel):
    answer: str = Field(description="A plain-English answer grounded only in the provided context.")
    citations: list[Citation] = Field(
        description="The sources and sections that directly support the answer; never empty."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in the answer given the provided context."
    )
    is_informational: Literal[True] = Field(
        default=True,
        description="Always true: this is informational, not legal or financial advice.",
    )


class ParcelSummary(BaseModel):
    summary: str = Field(
        description=(
            "One short paragraph (3-5 sentences), plain-English read of this parcel for an "
            "investor or builder, using ONLY the provided FACTS."
        )
    )
    is_informational: Literal[True] = Field(
        default=True,
        description="Always true: this is informational, not legal or financial advice.",
    )


class ParcelSummaryResult(BaseModel):
    parcel_number: str
    verdict_version: str
    summary: str
    data_coverage: Literal["high", "medium", "low"]
    is_informational: bool
    sources: list[dict[str, Any]]
    computed_at: datetime


class ReportSection(BaseModel):
    heading: str = Field(
        description=(
            "Short section title, e.g. 'Overview', 'Buildability', 'Valuation & deal', 'Risks'."
        )
    )
    body: str = Field(
        description="Two to four sentences for this section, using ONLY the provided FACTS."
    )


class ParcelReport(BaseModel):
    headline: str = Field(
        description="One-sentence investment thesis for the parcel, drawn only from the FACTS."
    )
    sections: list[ReportSection] = Field(
        description=(
            "The memo sections in order — Overview, Buildability, Valuation & deal, Risks. "
            "Omit a section only when the FACTS contain nothing to support it."
        )
    )
    recommendation: str = Field(
        description=(
            "A short, neutral, non-promotional next-step read grounded only in the FACTS, "
            "framed as informational."
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence that reflects how complete the provided FACTS are."
    )
    is_informational: Literal[True] = Field(
        default=True,
        description="Always true: this is informational, not legal or financial advice.",
    )


class ParcelReportResult(BaseModel):
    parcel_number: str
    headline: str
    sections: list[ReportSection]
    recommendation: str
    confidence: Literal["high", "medium", "low"]
    is_informational: bool
    sources: list[dict[str, Any]]
    computed_at: datetime
