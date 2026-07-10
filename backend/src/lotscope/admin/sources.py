from lotscope.admin.schemas import FetchSource
from lotscope.ingestion.loaders.hbg import CITY_ARCGIS
from lotscope.ingestion.loaders.hbg_repository import REPOSITORY_PDF_URL

KNOWN_SOURCES: list[FetchSource] = [
    FetchSource(
        label="Dauphin repository list (PDF)",
        url=REPOSITORY_PDF_URL,
        description="Master repository property list published by Dauphin County.",
    ),
    FetchSource(
        label="Harrisburg city GIS catalog (JSON)",
        url=f"{CITY_ARCGIS}?f=json",
        description="Lists every Harrisburg city ArcGIS feature service and its layers.",
    ),
    FetchSource(
        label="Harrisburg historic districts (GeoJSON)",
        url=f"{CITY_ARCGIS}/MunicipalHD/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson",
        description="All historic district polygons from the city GIS hub.",
    ),
    FetchSource(
        label="Harrisburg neighborhood associations (GeoJSON)",
        url=(
            f"{CITY_ARCGIS}/Neighborhood_Associations/FeatureServer/0/query"
            "?where=1%3D1&outFields=*&f=geojson"
        ),
        description="All neighborhood-association polygons from the city GIS hub.",
    ),
]
