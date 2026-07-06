from lotscope.checklist.logic import _RISK_CATEGORIES, _risk_item
from lotscope.markets.capabilities import (
    checklist_category_state,
    checklist_state_detail,
    forced_sale_label,
)
from lotscope.risk.scoring import RiskFlag
from lotscope.risk.service import _flag_schema


def test_hbg_category_states_are_distinct() -> None:
    assert checklist_category_state("hbg", "li") == "no_data_source"
    assert checklist_category_state("hbg", "flood") == "pending_load"
    assert checklist_category_state("hbg", "overlays") == "pending_load"
    assert checklist_category_state("hbg", "liens_taxes") == "available"
    assert checklist_category_state("phl", "li") == "available"


def test_no_data_source_names_the_market_reason_not_a_pass() -> None:
    code, category, flag_codes, clear = next(c for c in _RISK_CATEGORIES if c[0] == "li")
    detail = checklist_state_detail("hbg", "li", "no_data_source")
    item = _risk_item(
        code, category, flag_codes, clear, [], availability="no_data_source", state_detail=detail
    )
    assert item.status == "info"
    assert item.availability == "no_data_source"
    assert "code-enforcement" in item.detail


def test_pending_load_says_loading_not_no_source() -> None:
    code, category, flag_codes, clear = next(c for c in _RISK_CATEGORIES if c[0] == "flood")
    detail = checklist_state_detail("hbg", "flood", "pending_load")
    item = _risk_item(
        code, category, flag_codes, clear, [], availability="pending_load", state_detail=detail
    )
    assert item.availability == "pending_load"
    assert "loaded" in item.detail.lower()


def test_available_category_with_no_flags_still_passes() -> None:
    code, category, flag_codes, clear = next(c for c in _RISK_CATEGORIES if c[0] == "li")
    item = _risk_item(code, category, flag_codes, clear, [])
    assert item.status == "pass"
    assert item.availability == "available"


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
