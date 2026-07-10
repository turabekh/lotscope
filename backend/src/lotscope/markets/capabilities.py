_CHECKLIST_CATEGORY_STATE: dict[str, dict[str, str]] = {
    "hbg": {
        "li": "no_data_source",
        "liens_taxes": "pending_load",
    },
    "pgh": {
        "flood": "pending_load",
        "access": "pending_load",
        "overlays": "pending_load",
    },
}

_NO_SOURCE_DETAIL: dict[tuple[str, str], str] = {
    ("hbg", "li"): "Harrisburg does not publish a code-enforcement / violations dataset.",
}

# Flip an entry on once the PA Right-to-Know Law request is filed for that market/category.
_RTKL_FILED: frozenset[tuple[str, str]] = frozenset()

_PENDING_DETAIL: dict[tuple[str, str], str] = {
    ("pgh", "flood"): "FEMA flood-zone data is not yet loaded for Pittsburgh; "
    "flood exposure is unconfirmed for this parcel.",
    ("pgh", "access"): "Street-centerline data is not yet loaded for Pittsburgh; "
    "street frontage and landlocked status are unconfirmed for this parcel.",
    ("pgh", "overlays"): "Historic-district and zoning-overlay data is not yet loaded for "
    "Pittsburgh; extra design-review requirements are unconfirmed for this parcel.",
    ("hbg", "liens_taxes"): (
        "Dauphin County publishes delinquency through its annual tax-sale lists; "
        "the 2026 upset-sale list publishes in August. Delinquency is not yet loaded "
        "for Harrisburg, so this is not a clean-title confirmation."
    ),
}

# Markets whose risk pillar covers only a subset of the feeds Philadelphia has;
# the display carries this honest qualifier.
_RISK_COVERAGE_NOTE: dict[str, str] = {
    "hbg": "based on available Harrisburg sources",
}


def risk_coverage_note(market_code: str) -> str | None:
    return _RISK_COVERAGE_NOTE.get(market_code)


# Categories whose Philadelphia clear-detail wording references concepts a market
# lacks (e.g. RCO is a Philadelphia Title-14 construct) get a market-neutral clear detail.
_CLEAR_DETAIL_OVERRIDE: dict[tuple[str, str], str] = {
    ("hbg", "overlays"): "Not in a historic district requiring extra design review.",
}


def checklist_category_state(market_code: str, category: str) -> str:
    return _CHECKLIST_CATEGORY_STATE.get(market_code, {}).get(category, "available")


def checklist_state_detail(market_code: str, category: str, state: str) -> str:
    table = _NO_SOURCE_DETAIL if state == "no_data_source" else _PENDING_DETAIL
    default = (
        "No data source for this market."
        if state == "no_data_source"
        else "This dataset is being loaded for this market."
    )
    detail = table.get((market_code, category), default)
    if state == "no_data_source" and (market_code, category) in _RTKL_FILED:
        detail += " Records requested under the PA Right-to-Know Law."
    return detail


def clear_detail_override(market_code: str, category: str) -> str | None:
    return _CLEAR_DETAIL_OVERRIDE.get((market_code, category))


_FORCED_SALE_LABEL: dict[str, str] = {
    "phl": "Sheriff sale",
    "hbg": "Tax sale (RETSL)",
    "pgh": "Treasurer's sale",
}

_FORCED_SALE_SURFACE_LABEL: dict[str, str] = {
    "phl": "Sheriff sales",
    "hbg": "Tax sales",
    "pgh": "Treasurer's sale",
}


def forced_sale_surface_label(market_code: str) -> str:
    return _FORCED_SALE_SURFACE_LABEL.get(market_code, "Sheriff sales")


_DISPLAY_NAME: dict[str, str] = {
    "phl": "Philadelphia",
    "hbg": "Harrisburg",
}

_ZONING_CITATION: dict[str, str] = {
    "phl": "Title 14",
    "hbg": "Harrisburg Zoning Code",
    "pgh": "Pittsburgh Zoning Code",
}

_HIDDEN_SURFACES: dict[str, frozenset[str]] = {
    "hbg": frozenset({"zba_variance"}),
    "pgh": frozenset({"zba_variance", "sheriff_sales", "owner_portfolio"}),
}


def market_display_name(market_code: str) -> str:
    return _DISPLAY_NAME.get(market_code, market_code)


def zoning_citation_label(market_code: str) -> str:
    return _ZONING_CITATION.get(market_code, "the zoning code")


def hidden_surfaces(market_code: str) -> frozenset[str]:
    return _HIDDEN_SURFACES.get(market_code, frozenset())


def forced_sale_label(market_code: str) -> str:
    return _FORCED_SALE_LABEL.get(market_code, "Forced-sale pipeline")
