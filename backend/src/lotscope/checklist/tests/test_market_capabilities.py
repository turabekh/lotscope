from lotscope.checklist.logic import _RISK_CATEGORIES, _risk_item
from lotscope.markets.capabilities import (
    forced_sale_label,
    unsupported_checklist_categories,
)
from lotscope.risk.scoring import RiskFlag
from lotscope.risk.service import _flag_schema


def test_hbg_marks_li_and_overlays_unsupported() -> None:
    assert unsupported_checklist_categories("hbg") == {"li", "overlays", "flood"}
    assert unsupported_checklist_categories("phl") == frozenset()


def test_unsupported_category_renders_no_data_source_not_pass() -> None:
    code, category, flag_codes, clear = next(c for c in _RISK_CATEGORIES if c[0] == "li")
    item = _risk_item(code, category, flag_codes, clear, [], unsupported=True)
    assert item.status == "info"
    assert item.detail == "No data source for this market."
    assert item.status != "pass"


def test_supported_category_with_no_flags_still_passes() -> None:
    code, category, flag_codes, clear = next(c for c in _RISK_CATEGORIES if c[0] == "li")
    item = _risk_item(code, category, flag_codes, clear, [], unsupported=False)
    assert item.status == "pass"


def test_forced_sale_flag_relabelled_retsl_for_hbg() -> None:
    flag = RiskFlag("sheriff_sale", "high", "Sheriff-sale exposure", "Parcel is flagged.", "tax")
    phl = _flag_schema(flag, "phl")
    hbg = _flag_schema(flag, "hbg")
    assert phl.label == "Sheriff-sale exposure"
    assert "RETSL" in hbg.label
    assert forced_sale_label("hbg") in hbg.detail


def test_display_name_citation_and_hidden_surfaces() -> None:
    from lotscope.ai.prompts import SUMMARY_SYSTEM_PROMPT, for_market
    from lotscope.markets.capabilities import (
        hidden_surfaces,
        market_display_name,
        zoning_citation_label,
    )

    assert market_display_name("phl") == "Philadelphia"
    assert market_display_name("hbg") == "Harrisburg"
    assert zoning_citation_label("phl") == "Title 14"
    assert zoning_citation_label("hbg") == "Harrisburg Zoning Code"
    assert hidden_surfaces("hbg") == {"zba_variance", "sheriff_sales"}
    assert hidden_surfaces("phl") == frozenset()
    # prompts carry the market city, not a hardcoded literal
    assert "Harrisburg real estate" in for_market(SUMMARY_SYSTEM_PROMPT, "Harrisburg")
    assert "Philadelphia real estate" in for_market(SUMMARY_SYSTEM_PROMPT, "Philadelphia")
