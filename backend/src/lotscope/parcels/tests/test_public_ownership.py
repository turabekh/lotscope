from lotscope.parcels.public_ownership import is_public_owner


def test_city_and_agency_owners_are_public() -> None:
    assert is_public_owner("CITY OF PHILA") is True
    assert is_public_owner("CITY OF PHILADELPHIA") is True
    assert is_public_owner("CITY OF PHILA TRUSTEE") is True
    assert is_public_owner("PHILADELPHIA HOUSING AUTH") is True
    assert is_public_owner("PHILADELPHIA LAND BANK") is True
    assert is_public_owner("REDEVELOPMENT AUTHORITY") is True
    assert is_public_owner("PHDC") is True


def test_upstream_misspellings_are_still_public() -> None:
    assert is_public_owner("CITY OF PHILADEELPHIA") is True
    assert is_public_owner("CITY OF PHILADEPLPHIA") is True
    assert is_public_owner("CITY OF PHILADELPIA") is True
    assert is_public_owner("PHIADELPHIA LAND BANK") is True


def test_case_and_spacing_do_not_matter() -> None:
    assert is_public_owner("City of Philadelphia") is True
    assert is_public_owner("  CITY  OF   PHILA  ") is True


def test_private_companies_that_read_public_are_not_public() -> None:
    assert is_public_owner("WEST PHILADELPHIA HOUSING GROUP LLC") is False
    assert is_public_owner("PHILADELPHIA HOUSING GROUP LLC") is False
    assert is_public_owner("HLP PHILADELPHIA HOUSING") is False


def test_ordinary_owners_are_not_public() -> None:
    assert is_public_owner("SMITH WILLIAM") is False
    assert is_public_owner("ASBELL WILLIAM;ASBELL DORA") is False
    assert is_public_owner("PHILADELPHIA ENERGY SOLUTIONS") is False
    assert is_public_owner(None) is False
    assert is_public_owner("") is False
