from datetime import datetime

from lotscope.core.provenance import FieldProvenance, calculated, estimated, unavailable
from lotscope.deal.schemas import DealResult
from lotscope.valuation.schemas import ValuationResult
from lotscope.zoning.schemas import BuildabilityResult

_DISTRICT_METHOD_VERSION = "adr-0056"
_ENVELOPE_METHOD_VERSION = "adr-0011"
_AVM_METHOD_VERSION = "adr-0045"
_DEAL_METHOD_VERSION = "adr-0022"

_NO_BUILDABILITY = "Buildability was not evaluated for this parcel."
_NO_DISTRICT = "No zoning district resolved, so base-district standards were not applied."
_NO_VALUATION = "Valuation was not evaluated for this parcel."
_NO_COMPS = "No arm's-length comparable sales met the filters, so no estimate was produced."
_NO_DEAL = "Deal economics were not evaluated for this parcel."
_NO_ASSESSMENT = "No assessed market value on record, so the gap could not be calculated."

SourceAges = dict[str, datetime | None]


def _zoning_provenance(
    buildability: BuildabilityResult | None, ages: SourceAges, value: object
) -> FieldProvenance:
    if buildability is None:
        return unavailable(_NO_BUILDABILITY)
    if buildability.district_code is None or value is None:
        return unavailable(_NO_DISTRICT, source_label="zoning_district")
    return calculated(
        "zoning_district",
        method_version=_DISTRICT_METHOD_VERSION,
        as_of=ages.get("zoning_district"),
    )


def _envelope_provenance(
    buildability: BuildabilityResult | None, ages: SourceAges
) -> FieldProvenance:
    if buildability is None:
        return unavailable(_NO_BUILDABILITY)
    if buildability.buildable_area_sqft is None:
        return unavailable(
            "Buildable area could not be derived from the parcel geometry and standards.",
            source_label="pwd_parcel",
        )
    return calculated(
        "pwd_parcel", method_version=_ENVELOPE_METHOD_VERSION, as_of=ages.get("pwd_parcel")
    )


def _valuation_provenance(valuation: ValuationResult | None, ages: SourceAges) -> FieldProvenance:
    if valuation is None:
        return unavailable(_NO_VALUATION)
    if valuation.estimate is None:
        return unavailable(_NO_COMPS, source_label="rtt_summary")
    return estimated(
        "rtt_summary",
        confidence=valuation.confidence,
        method_version=_AVM_METHOD_VERSION,
        as_of=ages.get("rtt_summary"),
    )


def _deal_provenance(deal: DealResult | None, value: object, ages: SourceAges) -> FieldProvenance:
    if deal is None:
        return unavailable(_NO_DEAL)
    if value is None:
        return unavailable(
            "A required underwriting input was unavailable, so this figure was not calculated.",
            source_label="rtt_summary",
        )
    return estimated(
        "rtt_summary",
        confidence=deal.confidence,
        method_version=_DEAL_METHOD_VERSION,
        as_of=ages.get("rtt_summary"),
    )


def compose_field_trust(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    deal: DealResult | None,
    *,
    assessment_market_gap: float | None,
    source_ages: SourceAges,
) -> dict[str, FieldProvenance]:
    by_right_units = buildability.by_right_units if buildability is not None else None
    max_height_ft = buildability.max_height_ft if buildability is not None else None
    can_build = buildability.can_build_by_right if buildability is not None else None

    trust: dict[str, FieldProvenance] = {
        "can_build_by_right": _zoning_provenance(buildability, source_ages, can_build),
        "by_right_units": _zoning_provenance(buildability, source_ages, by_right_units),
        "max_height_ft": _zoning_provenance(buildability, source_ages, max_height_ft),
        "buildable_area_sqft": _envelope_provenance(buildability, source_ages),
        "value_estimate_low": _valuation_provenance(valuation, source_ages),
        "value_estimate_high": _valuation_provenance(valuation, source_ages),
        "arv": _deal_provenance(deal, deal.arv if deal is not None else None, source_ages),
        "est_profit": _deal_provenance(
            deal, deal.profit if deal is not None else None, source_ages
        ),
        "est_margin": _deal_provenance(
            deal, deal.margin if deal is not None else None, source_ages
        ),
        "max_allowable_offer": _deal_provenance(
            deal, deal.max_allowable_offer if deal is not None else None, source_ages
        ),
    }

    if assessment_market_gap is None:
        trust["assessment_market_gap"] = unavailable(_NO_ASSESSMENT)
    else:
        trust["assessment_market_gap"] = calculated(
            "opa_properties_public",
            method_version=_AVM_METHOD_VERSION,
            as_of=source_ages.get("opa_properties_public"),
        )

    return trust
