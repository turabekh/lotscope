from lotscope.parcels.abatement import has_active_exemption


def test_exempt_building_signals_active_exemption() -> None:
    assert has_active_exemption(None, 120000.0) is True


def test_exempt_land_signals_active_exemption() -> None:
    assert has_active_exemption(5000.0, None) is True


def test_no_exemption_when_zero_or_missing() -> None:
    assert has_active_exemption(None, None) is False
    assert has_active_exemption(0.0, 0.0) is False
