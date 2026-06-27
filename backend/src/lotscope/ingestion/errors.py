from lotscope.core.errors import UpstreamError


class IngestionError(UpstreamError):
    default_message = "Ingestion failed."


class CartoError(IngestionError):
    default_message = "The Carto SQL API request failed."


class ArcGisError(IngestionError):
    default_message = "The ArcGIS Hub request failed."
