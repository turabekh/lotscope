_UNSUPPORTED_CHECKLIST_CATEGORIES: dict[str, frozenset[str]] = {
    "hbg": frozenset({"li", "overlays", "flood"}),
}

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


def unsupported_checklist_categories(market_code: str) -> frozenset[str]:
    return _UNSUPPORTED_CHECKLIST_CATEGORIES.get(market_code, frozenset())


def forced_sale_label(market_code: str) -> str:
    return _FORCED_SALE_LABEL.get(market_code, "Forced-sale pipeline")
