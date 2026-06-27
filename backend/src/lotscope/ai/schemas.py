from typing import Literal

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
        description="Always true: this is informational, not legal or financial advice."
    )
