from lotscope.documents.links import philadox_document_url

_TEMPLATE = "https://records.test/document/InstrumentID={document_id}&Guest=true"


def test_builds_url_from_document_id() -> None:
    url = philadox_document_url(_TEMPLATE, "53772373")
    assert url == "https://records.test/document/InstrumentID=53772373&Guest=true"


def test_trims_and_escapes_document_id() -> None:
    url = philadox_document_url(_TEMPLATE, " 537 72373 ")
    assert url is not None
    assert "InstrumentID=537%2072373" in url


def test_returns_none_for_missing_document_id() -> None:
    assert philadox_document_url(_TEMPLATE, None) is None
    assert philadox_document_url(_TEMPLATE, "") is None
