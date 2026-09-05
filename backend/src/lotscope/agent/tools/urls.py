from urllib.parse import quote

ATLAS = "https://atlas.phila.gov/{parcel}"
CARTO_TABLE = "https://opendataphilly.org/datasets/{slug}/"
LI_SEARCH = "https://li.phila.gov/property-history/search?address={address}"
CIVILVIEW = "https://philadelphia.sheriffsale.com/"
PHILLYCODE_PROVISION = "https://codelibrary.amlegal.com/codes/philadelphia/latest/search?q={cite}"

OPA_URL = CARTO_TABLE.format(slug="philadelphia-properties-and-assessments")
RTT_URL = CARTO_TABLE.format(slug="real-estate-transfers")
LI_URL = CARTO_TABLE.format(slug="licenses-and-inspections-violations")
TAX_URL = CARTO_TABLE.format(slug="real-estate-tax-delinquencies")
ZONING_URL = CARTO_TABLE.format(slug="zoning-base-districts")
OVERLAY_URL = CARTO_TABLE.format(slug="zoning-overlays")
RCO_URL = CARTO_TABLE.format(slug="zoning-rco")
HISTORIC_URL = CARTO_TABLE.format(slug="philadelphia-historic-districts")
FLOOD_URL = "https://msc.fema.gov/portal/home"
PWD_URL = CARTO_TABLE.format(slug="pwd-stormwater-billing-parcels")


def atlas(parcel_number: str) -> str:
    local = parcel_number.split(":", 1)[-1]
    return ATLAS.format(parcel=quote(local))


def li_history(address: str | None) -> str:
    if not address:
        return LI_URL
    return LI_SEARCH.format(address=quote(address))


def provision(cite: str | None) -> str:
    if not cite:
        return PHILLYCODE_PROVISION.format(cite="")
    return PHILLYCODE_PROVISION.format(cite=quote(cite))
