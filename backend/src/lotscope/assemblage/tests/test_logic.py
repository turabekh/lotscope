from lotscope.assemblage.logic import (
    NeighborSignal,
    TargetLot,
    assess_potential,
    build_reasons,
    classify_acquirability,
    is_candidate,
    summarize,
)


def _neighbor(
    parcel_number: str = "n1",
    *,
    same_owner: bool = False,
    same_zoning: bool = True,
    is_vacant: bool = False,
    is_city_owned: bool = False,
    lot_area_sqft: float | None = 1000.0,
    frontage_ft: float | None = 20.0,
) -> NeighborSignal:
    return NeighborSignal(
        parcel_number=parcel_number,
        same_owner=same_owner,
        same_zoning=same_zoning,
        is_vacant=is_vacant,
        is_city_owned=is_city_owned,
        lot_area_sqft=lot_area_sqft,
        frontage_ft=frontage_ft,
    )


def test_acquirability_priority_order() -> None:
    assert classify_acquirability(_neighbor(same_owner=True, is_vacant=True)) == "same_owner"
    assert classify_acquirability(_neighbor(is_city_owned=True, is_vacant=True)) == "city_owned"
    assert classify_acquirability(_neighbor(is_vacant=True)) == "vacant"
    assert classify_acquirability(_neighbor()) == "built"


def test_candidate_requires_same_zoning_and_acquirable() -> None:
    assert is_candidate(_neighbor(is_vacant=True, same_zoning=True))
    assert not is_candidate(_neighbor(is_vacant=True, same_zoning=False))
    assert not is_candidate(_neighbor(same_zoning=True))


def test_summary_combines_target_and_candidate_dimensions() -> None:
    target = TargetLot(lot_area_sqft=1600.0, frontage_ft=18.0)
    neighbors = [
        _neighbor("n1", is_vacant=True, lot_area_sqft=1600.0, frontage_ft=18.0),
        _neighbor("n2", is_vacant=False, lot_area_sqft=2000.0),  # built -> not candidate
    ]
    summary = summarize(target, neighbors)
    assert summary.adjacent_count == 2
    assert summary.candidate_count == 1
    assert summary.combined_lot_area_sqft == 3200.0
    assert summary.combined_frontage_ft == 36.0
    assert summary.has_vacant_neighbor is True


def test_potential_high_for_same_owner_neighbor() -> None:
    assert assess_potential([_neighbor(same_owner=True)]) == "high"


def test_potential_high_for_two_candidates() -> None:
    assert assess_potential([_neighbor("a", is_vacant=True), _neighbor("b", is_vacant=True)]) == (
        "high"
    )


def test_potential_medium_for_single_vacant_candidate() -> None:
    assert assess_potential([_neighbor(is_vacant=True)]) == "medium"


def test_potential_none_without_candidates() -> None:
    assert assess_potential([_neighbor(is_vacant=True, same_zoning=False)]) == "none"
    assert assess_potential([]) == "none"


def test_reasons_explain_candidates() -> None:
    target = TargetLot(lot_area_sqft=1600.0, frontage_ft=18.0)
    reasons = build_reasons(target, [_neighbor(is_city_owned=True, lot_area_sqft=1600.0)])
    assert any("city or Land Bank" in r for r in reasons)
    assert any("contiguous" in r for r in reasons)
