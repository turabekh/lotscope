_UNSUPPORTED_CHECKLIST_CATEGORIES: dict[str, frozenset[str]] = {
    "hbg": frozenset({"li", "overlays", "flood"}),
}

_FORCED_SALE_LABEL: dict[str, str] = {
    "phl": "Sheriff sale",
    "hbg": "Tax sale (RETSL)",
}


def unsupported_checklist_categories(market_code: str) -> frozenset[str]:
    return _UNSUPPORTED_CHECKLIST_CATEGORIES.get(market_code, frozenset())


def forced_sale_label(market_code: str) -> str:
    return _FORCED_SALE_LABEL.get(market_code, "Forced-sale pipeline")
