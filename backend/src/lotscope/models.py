from lotscope.ai.models import Document
from lotscope.core.db import Base
from lotscope.ingestion.models import DatasetFreshness
from lotscope.parcels.models import Parcel
from lotscope.risk.models import FloodZone, LiEvent, TaxStatus
from lotscope.valuation.models import Sale
from lotscope.verdict.models import ParcelVerdict
from lotscope.zoning.models import ZoningDistrict, ZoningStandard

metadata = Base.metadata

__all__ = [
    "DatasetFreshness",
    "Document",
    "FloodZone",
    "LiEvent",
    "Parcel",
    "ParcelVerdict",
    "Sale",
    "TaxStatus",
    "ZoningDistrict",
    "ZoningStandard",
    "metadata",
]
