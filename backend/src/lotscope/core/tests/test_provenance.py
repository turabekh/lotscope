from datetime import UTC, datetime

import pytest

from lotscope.core.provenance import (
    STANDARDS_SOURCE_LABEL,
    UnknownSourceLabelError,
    calculated,
    datasets_for_source,
    estimated,
    mapped_source_labels,
    oldest_as_of,
    unavailable,
    verified,
)


def test_verified_requires_an_identified_source() -> None:
    with pytest.raises(ValueError, match="identified source_label"):
        verified("")
    assert verified("pwd_parcel").source_label == "pwd_parcel"


def test_a_derived_source_cannot_be_called_verified() -> None:
    with pytest.raises(ValueError, match="not an authoritative source"):
        verified("zoning_district")
    with pytest.raises(ValueError, match="not an authoritative source"):
        verified(STANDARDS_SOURCE_LABEL)


def test_resolved_zoning_is_calculated_not_verified() -> None:
    provenance = calculated("zoning_district", method_version="adr-0056")
    assert provenance.status == "calculated"
    assert provenance.default_origin == "derived"


def test_unavailable_must_state_why() -> None:
    with pytest.raises(ValueError, match="must state why"):
        unavailable("")
    assert unavailable("No street centerline loaded.").limitations is not None


def test_estimated_carries_confidence() -> None:
    provenance = estimated("rtt_summary", confidence="low")
    assert provenance.status == "estimated"
    assert provenance.confidence == "low"


def test_one_to_many_and_renamed_datasets_resolve() -> None:
    assert datasets_for_source("li_event") == ("violations", "permits", "demolitions")
    assert datasets_for_source("parcel") == ("opa_properties_public", "pwd_parcels")
    assert datasets_for_source("flood_zone") == ("fema_flood",)
    assert datasets_for_source("street_centerline") == ("streets",)
    assert datasets_for_source("zoning_district") == ("zoning_base_districts",)


def test_seeded_standards_have_no_ingestion_dataset() -> None:
    assert datasets_for_source(STANDARDS_SOURCE_LABEL) == ()


def test_an_unmapped_source_raises_rather_than_reporting_no_age() -> None:
    with pytest.raises(UnknownSourceLabelError):
        datasets_for_source("invented_source")


def test_as_of_takes_the_oldest_contributing_source() -> None:
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 7, 1, tzinfo=UTC)
    assert oldest_as_of([newer, older]) == older


def test_a_missing_contributing_source_makes_the_composite_undated() -> None:
    assert oldest_as_of([datetime(2026, 7, 1, tzinfo=UTC), None]) is None
    assert oldest_as_of([]) is None


def test_every_verified_source_label_is_mapped_to_a_dataset() -> None:
    from lotscope.core.provenance import VERIFIED_SOURCE_LABELS

    unmapped = sorted(VERIFIED_SOURCE_LABELS - mapped_source_labels())
    assert unmapped == []
