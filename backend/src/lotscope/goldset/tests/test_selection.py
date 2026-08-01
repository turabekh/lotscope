from typing import get_args

from lotscope.goldset.schemas import ExpectedFacts, GoldCategory
from lotscope.goldset.selection import SELECTORS, merge_into_cases


def test_every_required_category_has_a_selector() -> None:
    required = set(get_args(GoldCategory))
    covered = {selector.category for selector in SELECTORS}

    assert covered == required


def test_no_selector_reads_our_own_verdict_output() -> None:
    for selector in SELECTORS:
        assert "parcel_verdict" not in selector.predicate
        assert "risk_flag" not in selector.predicate


def test_every_selector_explains_itself_to_a_reviewer() -> None:
    for selector in SELECTORS:
        assert selector.rationale.strip()
        assert selector.rationale.endswith(".")


def test_a_parcel_matching_several_categories_becomes_one_case() -> None:
    cases = merge_into_cases(
        {
            "phl:1": ["historic", "flood_exposure", "historic"],
            "phl:2": ["industrial"],
        }
    )

    assert len(cases) == 2
    assert cases[0].parcel_number == "phl:1"
    assert cases[0].categories == ["flood_exposure", "historic"]


def test_selected_cases_carry_no_expectations_and_are_unreviewed() -> None:
    cases = merge_into_cases({"phl:1": ["industrial"]})

    assert cases[0].expected == ExpectedFacts()
    assert cases[0].expected.is_empty()
    assert cases[0].review_status == "unreviewed"
    assert cases[0].reviewer is None
