from datetime import date

from lotscope.ingestion.loaders.historic import HistoricRecord, to_historic_row

_GEOJSON = (
    '{"type":"Polygon","coordinates":[[[-75.15,39.95],[-75.15,39.96],'
    "[-75.14,39.96],[-75.14,39.95],[-75.15,39.95]]]}"
)


def test_to_historic_row_maps_name_date_and_geometry() -> None:
    record = HistoricRecord(
        objectid=4, name="Old City", designated="2003-12-21T00:00:00Z", geom_geojson=_GEOJSON
    )
    row = to_historic_row(record)
    assert row is not None
    assert row["external_id"] == "4"
    assert row["name"] == "Old City"
    assert row["designated_date"] == date(2003, 12, 21)
    assert "geom_local" in row


def test_to_historic_row_skips_without_geometry_or_id() -> None:
    assert to_historic_row(HistoricRecord(objectid=1, name="X", geom_geojson=None)) is None
    assert to_historic_row(HistoricRecord(objectid=None, geom_geojson=_GEOJSON)) is None
