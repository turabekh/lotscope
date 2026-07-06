_CHECKLIST_CATEGORY_STATE: dict[str, dict[str, str]] = {
    "hbg": {
        "li": "no_data_source",
        "flood": "pending_load",
        "overlays": "pending_load",
    },
}

_NO_SOURCE_DETAIL: dict[tuple[str, str], str] = {
    ("hbg", "li"): "Harrisburg does not publish a code-enforcement / violations dataset.",
}

_PENDING_DETAIL: dict[tuple[str, str], str] = {
    ("hbg", "flood"): "FEMA flood-zone data is being loaded for Harrisburg.",
    ("hbg", "overlays"): "Historic-district data is being loaded for Harrisburg.",
}

# Categories whose Philadelphia clear-detail wording references concepts a market
# lacks (e.g. RCO is a Philadelphia Title-14 construct) get a market-neutral clear detail.
_CLEAR_DETAIL_OVERRIDE: dict[tuple[str, str], str] = {
    ("hbg", "overlays"): (
        "Not in a historic district or zoning overlay requiring extra design review."
    ),
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
    return table.get((market_code, category), default)


def clear_detail_override(market_code: str, category: str) -> str | None:
    return _CLEAR_DETAIL_OVERRIDE.get((market_code, category))

_FORCED_SALE_LABEL: dict[str, str] = {
    "phl": "Sheriff sale",
    "hbg": "Tax sale (RETSL)",
}

_DISPLAY_NAME: dict[str, str] = {
    "phl": "Philadelphia",
    "hbg": "Harrisburg",
}

_ZONING_CITATION: dict[str, str] = {
    "phl": "Title 14",
    "hbg": "Harrisburg Zoning Code",
}

_HIDDEN_SURFACES: dict[str, frozenset[str]] = {
    "hbg": frozenset({"zba_variance", "sheriff_sales"}),
}


def market_display_name(market_code: str) -> str:
    return _DISPLAY_NAME.get(market_code, market_code)


def zoning_citation_label(market_code: str) -> str:
    return _ZONING_CITATION.get(market_code, "the zoning code")


def hidden_surfaces(market_code: str) -> frozenset[str]:
    return _HIDDEN_SURFACES.get(market_code, frozenset())


def forced_sale_label(market_code: str) -> str:
    return _FORCED_SALE_LABEL.get(market_code, "Forced-sale pipeline")
