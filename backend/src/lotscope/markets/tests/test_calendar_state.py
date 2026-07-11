from lotscope.markets.capabilities import sale_calendar_state


def test_phl_live_when_upcoming() -> None:
    state, note = sale_calendar_state("phl", has_upcoming=True)
    assert state == "live"
    assert note is None


def test_phl_empty_when_no_upcoming() -> None:
    state, note = sale_calendar_state("phl", has_upcoming=False)
    assert state == "empty"
    assert note is not None
    assert "Philadelphia" in note


def test_hbg_seasonal_when_no_upcoming() -> None:
    state, note = sale_calendar_state("hbg", has_upcoming=False)
    assert state == "seasonal"
    assert note is not None
    assert "September" in note


def test_pgh_unavailable_because_surface_hidden() -> None:
    state, note = sale_calendar_state("pgh", has_upcoming=False)
    assert state == "unavailable"
    assert note is not None
    assert "Treasurer's sale" in note
