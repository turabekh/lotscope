from lotscope.core.errors import UpstreamError


class IngestionError(UpstreamError):
    default_message = "Ingestion failed."


class CartoError(IngestionError):
    default_message = "The Carto SQL API request failed."


class ArcGisError(IngestionError):
    default_message = "The ArcGIS Hub request failed."


class CkanError(IngestionError):
    default_message = "The CKAN datastore request failed."


class ExtractError(IngestionError):
    default_message = "The file extract download failed."
