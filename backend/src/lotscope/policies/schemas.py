from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_MAX_BODY = 200_000

REQUIRED_POLICIES: tuple[tuple[str, str], ...] = (
    ("terms", "Terms of Service"),
    ("privacy", "Privacy Policy"),
    ("disclaimers", "Disclaimers"),
    ("disclosures", "Data Sources and Disclosures"),
    ("refund", "Refund Policy"),
    ("corrections", "Data Correction Policy"),
)

REQUIRED_SLUGS: frozenset[str] = frozenset(slug for slug, _ in REQUIRED_POLICIES)


class PolicyWrite(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body_markdown: str = Field(min_length=1, max_length=_MAX_BODY)
    version: str = Field(min_length=1, max_length=40)
    effective_date: datetime


class PolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    body_markdown: str
    version: str
    effective_date: datetime
    published_at: datetime


class PolicySummary(BaseModel):
    slug: str
    title: str
    published: bool
    version: str | None = None
    effective_date: datetime | None = None
