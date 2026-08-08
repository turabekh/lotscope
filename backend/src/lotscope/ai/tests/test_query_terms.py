from lotscope.ai.query_terms import extract_cites, extract_districts, lexical_terms


def test_district_codes_are_recognised_hyphenated_or_not() -> None:
    assert extract_districts("What can I build in RSA-5?") == ["RSA-5"]
    assert extract_districts("rsa5 setbacks") == ["RSA-5"]
    assert extract_districts("CMX-2.5 height limit") == ["CMX-2.5"]


def test_the_longer_prefix_wins_so_rmx_is_not_read_as_rm() -> None:
    assert extract_districts("RMX-3 standards") == ["RMX-3"]
    assert extract_districts("RM-4 standards") == ["RM-4"]
    assert extract_districts("IRMX and ICMX-1") == ["ICMX-1"]


def test_a_district_is_reported_once_however_often_it_appears() -> None:
    assert extract_districts("RSA-5 versus RSA-5 again") == ["RSA-5"]


def test_prose_without_a_district_yields_nothing() -> None:
    assert extract_districts("how many parking spaces do I need") == []
    assert extract_districts("a lot of 5 units") == []


def test_cites_are_recognised_at_section_and_subsection_depth() -> None:
    assert extract_cites("what does 14-802 require") == ["14-802"]
    assert extract_cites("see 14-701(2)(b)") == ["14-701(2)(b)"]
    assert extract_cites("4.1-100 and 19-1301") == ["4.1-100", "19-1301"]


def test_a_district_code_is_not_mistaken_for_a_cite() -> None:
    assert extract_cites("RSA-5 dimensional standards") == []


def test_lexical_terms_puts_cites_before_districts() -> None:
    assert lexical_terms("does 14-802 apply in RSA-5?") == ["14-802", "RSA-5"]
    assert lexical_terms("nothing to match here") == []
