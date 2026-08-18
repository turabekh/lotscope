from lotscope.risk.party_match import match_parties


def test_the_same_name_matches_exactly() -> None:
    assert match_parties("MATUSOW JOSEPH", "MATUSOW JOSEPH").strength == "exact"


def test_case_punctuation_and_spacing_do_not_defeat_an_exact_match() -> None:
    assert match_parties("MATUSOW, JOSEPH", "  matusow joseph ").strength == "exact"


def test_a_reordered_name_is_partial_not_exact() -> None:
    result = match_parties("MATUSOW JOSEPH", "JOSEPH MATUSOW")

    assert result.strength == "partial"
    assert result.shared_tokens == ("JOSEPH", "MATUSOW")


def test_a_single_shared_surname_is_not_a_match() -> None:
    assert match_parties("MATUSOW JOSEPH", "MATUSOW RACHEL").strength == "none"


def test_two_unrelated_parties_do_not_match() -> None:
    assert match_parties("MATUSOW JOSEPH", "SHLAYEN RACHEL").strength == "none"


def test_a_missing_name_never_matches() -> None:
    assert match_parties(None, "SHLAYEN RACHEL").strength == "none"
    assert match_parties("SHLAYEN RACHEL", None).strength == "none"
    assert match_parties("", "").strength == "none"


def test_suffixes_and_articles_cannot_carry_a_match_alone() -> None:
    assert match_parties("SMITH JR", "JONES JR").strength == "none"
    assert match_parties("THE SMITH TRUST", "THE JONES TRUST").strength == "none"


def test_an_entity_sharing_two_real_tokens_is_partial() -> None:
    result = match_parties("ARCH STREET HOLDINGS LLC", "ARCH STREET LLC")

    assert result.strength == "partial"
    assert "ARCH" in result.shared_tokens
