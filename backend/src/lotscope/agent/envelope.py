from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    name: str = Field(description="The dataset or service the value came from.")
    url: str | None = Field(
        default=None, description="Where a person can check this value themselves."
    )
    fetched_at: datetime | None = Field(
        default=None,
        description=(
            "When this value was read live from the primary source, at answer time. "
            "Only live tools set this."
        ),
    )
    ingested_at: datetime | None = Field(
        default=None,
        description=(
            "When the nightly ingest last read this source successfully. A stored value is "
            "only as current as this timestamp."
        ),
    )
    computed_at: datetime | None = Field(
        default=None, description="When LotScope derived this value, for derived facts."
    )


class ToolResult(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict, description="The facts this tool found.")
    sources: list[Source] = Field(
        default_factory=list,
        description="One entry per dataset behind the data. Cite these, do not invent others.",
    )
    unverified: list[str] = Field(
        default_factory=list,
        description=(
            "Things this tool could not establish. Anything named here must be called "
            "unverified in your answer, never asserted."
        ),
    )

    def to_model_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


def empty(reason: str) -> ToolResult:
    return ToolResult(data={}, sources=[], unverified=[reason])
