from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FieldState = Literal["verified", "calculated", "estimated", "unavailable"]

DefaultOrigin = Literal[
    "authoritative_source",
    "derived",
    "platform_default",
    "user_override",
    "scenario_override",
]

VERIFIED_SOURCE_LABELS: frozenset[str] = frozenset(
    {
        "opa_properties_public",
        "pwd_parcel",
        "rtt_summary",
        "tax_status",
        "li_event",
        "flood_zone",
        "historicdistricts_local",
        "zoning_overlays",
        "zoning_rco",
        "street_centerline",
    }
)

_SOURCE_DATASETS: dict[str, tuple[str, ...]] = {
    "parcel": ("opa_properties_public", "pwd_parcels"),
    "pwd_parcel": ("pwd_parcels",),
    "opa_properties_public": ("opa_properties_public",),
    "zoning_district": ("zoning_base_districts",),
    "rtt_summary": ("rtt_summary",),
    "tax_status": ("real_estate_tax_delinquencies",),
    "li_event": ("violations", "permits", "demolitions"),
    "flood_zone": ("fema_flood",),
    "street_centerline": ("streets",),
    "historicdistricts_local": ("historicdistricts_local",),
    "zoning_overlays": ("zoning_overlays",),
    "zoning_rco": ("zoning_rco",),
}

STANDARDS_SOURCE_LABEL = "zoning_standard"


class UnknownSourceLabelError(LookupError):
    pass


def datasets_for_source(source_label: str) -> tuple[str, ...]:
    if source_label == STANDARDS_SOURCE_LABEL:
        return ()
    datasets = _SOURCE_DATASETS.get(source_label)
    if datasets is None:
        raise UnknownSourceLabelError(
            f"No dataset mapping registered for source label {source_label!r}."
        )
    return datasets


def mapped_source_labels() -> frozenset[str]:
    return frozenset(_SOURCE_DATASETS) | {STANDARDS_SOURCE_LABEL}


def oldest_as_of(candidates: list[datetime | None]) -> datetime | None:
    present = [value for value in candidates if value is not None]
    if not present or len(present) != len(candidates):
        return None
    return min(present)


class FieldProvenance(BaseModel):
    status: FieldState = Field(
        description="Trust state of this field: verified when an identified authoritative source "
        "reported it for this parcel, calculated when deterministically derived from identified "
        "inputs, estimated when model- or comparable-based, unavailable when not obtained, not "
        "evaluated, or insufficient."
    )
    source_label: str | None = Field(
        default=None,
        description="The internal source this value came from, or null when unavailable.",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Age of the oldest contributing source; null when no dated source applies.",
    )
    method_version: str | None = Field(
        default=None,
        description="Version of the rule or model that produced a calculated or estimated value.",
    )
    confidence: str | None = Field(
        default=None, description="Confidence signal for estimated values."
    )
    limitations: str | None = Field(
        default=None,
        description="Why this field is unavailable, or what the value does not account for.",
    )
    default_origin: DefaultOrigin | None = Field(
        default=None, description="Where the value originated when it is not source-reported."
    )

    def model_post_init(self, __context: object) -> None:
        if self.status == "verified" and not (self.source_label or "").strip():
            raise ValueError("A verified field requires an identified source_label.")
        if self.status == "verified" and self.source_label not in VERIFIED_SOURCE_LABELS:
            raise ValueError(
                f"Source {self.source_label!r} is not an authoritative source; a value derived "
                "from it is calculated, not verified."
            )
        if self.status == "unavailable" and not (self.limitations or "").strip():
            raise ValueError("An unavailable field must state why it is unavailable.")


def unavailable(limitations: str, *, source_label: str | None = None) -> FieldProvenance:
    return FieldProvenance(status="unavailable", source_label=source_label, limitations=limitations)


def verified(source_label: str, *, as_of: datetime | None = None) -> FieldProvenance:
    return FieldProvenance(
        status="verified",
        source_label=source_label,
        as_of=as_of,
        default_origin="authoritative_source",
    )


def calculated(
    source_label: str | None,
    *,
    method_version: str | None = None,
    as_of: datetime | None = None,
    limitations: str | None = None,
) -> FieldProvenance:
    return FieldProvenance(
        status="calculated",
        source_label=source_label,
        as_of=as_of,
        method_version=method_version,
        limitations=limitations,
        default_origin="derived",
    )


def estimated(
    source_label: str | None,
    *,
    confidence: str | None = None,
    method_version: str | None = None,
    as_of: datetime | None = None,
    limitations: str | None = None,
) -> FieldProvenance:
    return FieldProvenance(
        status="estimated",
        source_label=source_label,
        as_of=as_of,
        method_version=method_version,
        confidence=confidence,
        limitations=limitations,
        default_origin="derived",
    )
