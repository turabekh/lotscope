from enum import StrEnum

from pydantic import BaseModel, Field


class AskCoverage(StrEnum):
    SHARED = "shared"
    PHILLYCODE_ONLY = "phillycode_only"
    OUT_OF_CORPUS = "out_of_corpus"


class AskCategory(StrEnum):
    DISTRICT_DIMENSIONAL = "district_dimensional"
    DISTRICT_USE = "district_use"
    PARKING = "parking"
    PARKING_INDUSTRIAL = "parking_industrial"
    OVERLAY = "overlay"
    EXPLICIT_CITE = "explicit_cite"
    CROSS_REFERENCE = "cross_reference"
    OUT_OF_CORPUS = "out_of_corpus"


class AskCase(BaseModel):
    question_id: str
    question: str
    parcel_number: str
    category: AskCategory
    coverage: AskCoverage
    primary_cites: list[str] = Field(default_factory=list)
    acceptable_cites: list[str] = Field(default_factory=list)
    notes: str | None = None

    @property
    def expects_refusal(self) -> bool:
        return self.coverage is AskCoverage.OUT_OF_CORPUS
