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


def test_a_semicolon_pair_matches_on_either_party() -> None:
    result = match_parties("ASBELL WILLIAM", "ASBELL WILLIAM;ASBELL DORA")

    assert result.strength == "exact"
    assert result.shared_tokens == ("ASBELL", "WILLIAM")


def test_a_party_in_third_position_matches() -> None:
    result = match_parties("MCNAIR KENNETH", "CONNOR JOHN J;CONNOR JOHN J ESTATE OF;MCNAIR KENNETH")

    assert result.strength == "exact"
    assert result.shared_tokens == ("KENNETH", "MCNAIR")


def test_a_clean_party_match_inside_a_multi_party_string_is_full_not_partial() -> None:
    assert match_parties("SMITH MARGARET", "JONES ALBERT;SMITH MARGARET").strength == "exact"
    assert match_parties("SMITH MARGARET", "SMITH MARGARET").strength == "exact"


def test_a_multi_party_string_with_no_matching_party_does_not_match() -> None:
    result = match_parties("SHLAYEN RACHEL", "CONNOR JOHN J;CONNOR JOHN J ESTATE OF;MCNAIR KENNETH")

    assert result.strength == "none"
    assert result.shared_tokens == ()


def test_a_partial_overlap_inside_one_party_stays_partial() -> None:
    result = match_parties("ARCH STREET HOLDINGS LLC", "BAKER PROPERTIES;ARCH STREET LLC")

    assert result.strength == "partial"
    assert "ARCH" in result.shared_tokens
    assert "STREET" in result.shared_tokens


def test_the_strongest_party_match_wins_over_a_weaker_one() -> None:
    result = match_parties("SMITH WILLIAM", "SMITH WILLIAM WILKER;SMITH WILLIAM")

    assert result.strength == "exact"


def test_delimiters_that_are_name_internal_are_never_split() -> None:
    assert match_parties("K & K INVESTMENT CO", "K & K INVESTMENT CO").strength == "exact"
    assert (
        match_parties(
            "SECRETARY OF HOUSING AND URBAN DEVELOPMENT",
            "SECRETARY OF HOUSING AND URBAN DEVELOPMENT",
        ).strength
        == "exact"
    )
    assert match_parties("BAKER,ROTHSCHILD,INC", "BAKER,ROTHSCHILD,INC").strength == "exact"


def test_empty_parties_between_delimiters_are_ignored() -> None:
    assert match_parties("ASBELL WILLIAM", ";;ASBELL WILLIAM;;").strength == "exact"
    assert match_parties("ASBELL WILLIAM", ";;;").strength == "none"
