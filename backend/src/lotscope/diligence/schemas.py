from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["clear", "flag", "unverified"]

# The order the lines appear in, and the only lines there are. A diligence report that
# quietly drops a check a buyer expected is worse than one that says it could not run it,
# so every key here appears in every report — with "unverified" where we cannot see.
CHECK_KEYS: tuple[str, ...] = (
    "title_chain",
    "delinquency",
    "li_open_cases",
    "adjacent_unsafe",
    "conservatorship",
    "historic",
    "overlays_rco",
    "flood",
    "public_neighbour",
    "estate_probate",
    "party_wall",
    "utilities_curb",
    "sheriff",
)

CLOSING_BLOCK = (
    "Order a title search and a municipal lien letter before closing. Water Revenue and "
    "PGW liens are not visible to us: no dataset LotScope holds publishes them, so this "
    "report cannot tell you whether either exists on this parcel."
)


class DiligenceLine(BaseModel):
    """One check, and where its answer came from.

    A line carries fetched_at when it was read live from the primary source at the moment
    the report was made, and ingested_at when it came from our copy — never both, because
    a reader deciding whether to trust a line needs to know which of the two they have.
    """

    key: str
    label: str
    status: CheckStatus
    evidence: str
    source: str
    source_url: str | None = None
    fetched_at: datetime | None = None
    ingested_at: datetime | None = None


class DiligenceReport(BaseModel):
    parcel_number: str
    address: str | None
    lines: list[DiligenceLine] = Field(default_factory=list)
    closing: str = CLOSING_BLOCK
    computed_at: datetime

    @property
    def flags(self) -> int:
        return sum(1 for line in self.lines if line.status == "flag")

    @property
    def unverified(self) -> int:
        return sum(1 for line in self.lines if line.status == "unverified")
