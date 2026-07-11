from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.ingestion.arcgis import ArcGisClient
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.ckan import CkanDatastoreClient
from lotscope.ingestion.extract import ExtractClient
from lotscope.ingestion.filters import li_events_where, rtt_sales_where, zba_appeals_where
from lotscope.ingestion.loaders import (
    flood,
    hbg,
    hbg_repository,
    hbg_taxclaim,
    historic,
    li,
    neighborhoods,
    opa,
    overlays,
    pgh,
    pwd,
    rtt,
    sheriff,
    streets,
    tax,
    vacancy,
    zba,
    zoning,
)
from lotscope.ingestion.loaders.sheriff import CsvSheriffSource, SheriffSource, load_sheriff
from lotscope.ingestion.loaders.sheriff_civilview import CivilViewSheriffSource
from lotscope.ingestion.runner import run_loader
from lotscope.markets.models import Market

SessionFactory = async_sessionmaker[AsyncSession]
Job = Callable[[SessionFactory, Settings], Awaitable[int]]
ArcGisLoader = Callable[[AsyncSession, ArcGisClient], Awaitable[int]]


class CartoLoader(Protocol):
    def __call__(
        self, session: AsyncSession, carto: CartoClient, *, where: str | None = ...
    ) -> Awaitable[int]: ...


async def _run_carto(
    session_factory: SessionFactory,
    settings: Settings,
    *,
    loader: CartoLoader,
    dataset: str,
    where: str | None = None,
) -> int:
    async with CartoClient(settings) as carto:
        return await run_loader(
            session_factory, lambda session: loader(session, carto, where=where), dataset=dataset
        )


async def _run_arcgis(
    session_factory: SessionFactory,
    settings: Settings,
    *,
    loader: ArcGisLoader,
    dataset: str,
    market_code: str = "phl",
) -> int:
    async with ArcGisClient(settings) as arcgis:
        return await run_loader(
            session_factory,
            lambda session: loader(session, arcgis),
            dataset=dataset,
            market_code=market_code,
        )


async def ingest_opa(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(session_factory, settings, loader=opa.load_opa, dataset=opa.OPA_DATASET)


async def ingest_pwd(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(session_factory, settings, loader=pwd.load_pwd, dataset=pwd.PWD_DATASET)


async def ingest_rtt(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=rtt.load_rtt,
        dataset=rtt.RTT_DATASET,
        where=rtt_sales_where(settings.rtt_min_sale_date),
    )


async def ingest_tax(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(session_factory, settings, loader=tax.load_tax, dataset=tax.TAX_DATASET)


async def ingest_li_violations(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=li.load_li_violations,
        dataset=li.LI_VIOLATIONS_DATASET,
        where=li_events_where("violationdate", settings.li_min_event_date),
    )


async def ingest_li_permits(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=li.load_li_permits,
        dataset=li.LI_PERMITS_DATASET,
        where=li_events_where("permitissuedate", settings.li_min_event_date),
    )


async def ingest_li_demolitions(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=li.load_li_demolitions,
        dataset=li.LI_DEMOLITIONS_DATASET,
        where=li_events_where("start_date", settings.li_min_event_date),
    )


def _sheriff_source(settings: Settings) -> SheriffSource | None:
    if settings.sheriff_sale_source == "civilview":
        return CivilViewSheriffSource(settings)
    if settings.sheriff_sale_csv_path:
        return CsvSheriffSource(settings.sheriff_sale_csv_path)
    return None


async def ingest_sheriff(session_factory: SessionFactory, settings: Settings) -> int:
    source = _sheriff_source(settings)
    if source is None:
        return 0
    return await run_loader(
        session_factory,
        lambda session: load_sheriff(session, source),
        dataset=sheriff.SHERIFF_DATASET,
    )


async def ingest_zoning_overlays(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=overlays.load_zoning_overlays,
        dataset=overlays.ZONING_OVERLAY_DATASET,
    )


async def ingest_rco(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory, settings, loader=overlays.load_rco, dataset=overlays.RCO_DATASET
    )


async def ingest_zoning(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=zoning.load_zoning_districts,
        dataset=zoning.ZONING_DATASET,
    )


async def ingest_vacancy(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory, settings, loader=vacancy.load_vacancy, dataset=vacancy.VACANCY_DATASET
    )


async def ingest_flood(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory, settings, loader=flood.load_flood, dataset=flood.FLOOD_DATASET
    )


async def ingest_neighborhoods(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=neighborhoods.load_neighborhoods,
        dataset=neighborhoods.NEIGHBORHOODS_DATASET,
    )


async def ingest_streets(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory, settings, loader=streets.load_streets, dataset=streets.STREETS_DATASET
    )


async def ingest_historic(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=historic.load_historic,
        dataset=historic.HISTORIC_DATASET,
    )


async def ingest_zba(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_carto(
        session_factory,
        settings,
        loader=zba.load_zba,
        dataset=zba.ZBA_DATASET,
        where=zba_appeals_where(settings.zba_min_decision_date),
    )


async def _hbg_source_config(session_factory: SessionFactory) -> dict[str, Any]:
    async with session_factory() as session:
        market = await session.get(Market, "hbg")
        return dict(market.source_config) if market is not None else {}


async def ingest_hbg_parcels(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _hbg_source_config(session_factory)
    services_url = str(config["arcgis_services_url"])
    municipality = str(config["municipality_filter"])
    return await _run_arcgis(
        session_factory,
        settings,
        loader=lambda session, arcgis: hbg.load_hbg_parcels(
            session, arcgis, services_url=services_url, municipality=municipality
        ),
        dataset=hbg.HBG_PARCELS_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_sales(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _hbg_source_config(session_factory)
    services_url = str(config["arcgis_services_url"])
    return await _run_arcgis(
        session_factory,
        settings,
        loader=lambda session, arcgis: hbg.load_hbg_sales(
            session, arcgis, services_url=services_url
        ),
        dataset=hbg.HBG_SALES_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_zoning(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _hbg_source_config(session_factory)
    services_url = str(config["arcgis_services_url"])
    return await _run_arcgis(
        session_factory,
        settings,
        loader=lambda session, arcgis: hbg.load_hbg_zoning_districts(
            session, arcgis, services_url=services_url
        ),
        dataset=hbg.HBG_ZONING_DATASET,
        market_code="hbg",
    )


_PHL_JOBS: dict[str, Job] = {
    "opa": ingest_opa,
    "pwd": ingest_pwd,
    "rtt": ingest_rtt,
    "tax": ingest_tax,
    "li_violations": ingest_li_violations,
    "li_permits": ingest_li_permits,
    "li_demolitions": ingest_li_demolitions,
    "sheriff": ingest_sheriff,
    "zoning": ingest_zoning,
    "zoning_overlays": ingest_zoning_overlays,
    "rco": ingest_rco,
    "vacancy": ingest_vacancy,
    "flood": ingest_flood,
    "neighborhoods": ingest_neighborhoods,
    "streets": ingest_streets,
    "historic": ingest_historic,
    "zba": ingest_zba,
}


async def ingest_hbg_vacancy(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        hbg.derive_hbg_vacancy,
        dataset=hbg.HBG_VACANCY_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_streets(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _hbg_source_config(session_factory)
    services_url = str(config["arcgis_services_url"])
    return await _run_arcgis(
        session_factory,
        settings,
        loader=lambda session, arcgis: hbg.load_hbg_streets(
            session, arcgis, services_url=services_url
        ),
        dataset=hbg.HBG_STREETS_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_public(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        hbg.derive_hbg_public_ownership,
        dataset=hbg.HBG_PUBLIC_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_flood(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=hbg.load_hbg_flood,
        dataset=hbg.HBG_FLOOD_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_dimensions(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        hbg.derive_hbg_lot_width,
        dataset=hbg.HBG_DIMENSIONS_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_historic(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=hbg.load_hbg_historic,
        dataset=hbg.HBG_HISTORIC_DATASET,
        market_code="hbg",
    )


async def ingest_hbg_neighborhoods(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_arcgis(
        session_factory,
        settings,
        loader=hbg.load_hbg_neighborhoods,
        dataset=hbg.HBG_NEIGHBORHOODS_DATASET,
        market_code="hbg",
    )


_REPO_CSV_FIXTURE = (
    Path(__file__).resolve().parents[4] / "docs" / "dauphin-repository-list-2026-06-25.csv"
)


def _pdf_text(content: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def ingest_hbg_repository(session_factory: SessionFactory, settings: Settings) -> int:
    logger = get_logger("ingestion.hbg_repository")
    rows: list[dict[str, Any]] | None = None
    try:
        async with ExtractClient(settings) as extract:
            download = await extract.download(hbg_repository.REPOSITORY_PDF_URL)
        parsed = hbg_repository.parse_repository_pdf_text(_pdf_text(download.content))
        if parsed:
            rows = parsed
            logger.info("hbg_repository_source", source="prod_pdf", rows=len(parsed))
    except Exception as exc:
        logger.warning("hbg_repository_pdf_unavailable", error=str(exc))
    if rows is None and _REPO_CSV_FIXTURE.exists():
        rows = hbg_repository.read_repository_csv(_REPO_CSV_FIXTURE)
        logger.info("hbg_repository_source", source="csv_fixture", rows=len(rows))
    if not rows:
        return 0
    async with session_factory() as session:
        result = await hbg_repository.load_hbg_repository(session, rows)
        await session.commit()
    return result.loaded


async def ingest_hbg_tax_claim(
    session_factory: SessionFactory, settings: Settings, *, list_url: str, list_date: date
) -> int:
    async with ExtractClient(settings) as extract:
        return await run_loader(
            session_factory,
            lambda session: hbg_taxclaim.load_hbg_tax_claim(
                session, extract, list_url=list_url, list_date=list_date
            ),
            dataset=hbg_taxclaim.HBG_TAX_CLAIM_DATASET,
            market_code="hbg",
        )


async def _pgh_source_config(session_factory: SessionFactory) -> dict[str, Any]:
    async with session_factory() as session:
        market = await session.get(Market, "pgh")
        return dict(market.source_config) if market is not None else {}


async def ingest_pgh_parcels(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    resource_id = str(config["assessment_resource_id"])
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: pgh.load_pgh_parcels(session, ckan, resource_id=resource_id),
            dataset=pgh.PGH_PARCELS_DATASET,
            market_code="pgh",
        )


async def ingest_pgh_geometry(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: pgh.load_pgh_geometry(
                session,
                ckan,
                boundaries_resource_id=str(config["boundaries_resource_id"]),
                assessment_resource_id=str(config["assessment_resource_id"]),
            ),
            dataset=pgh.PGH_GEOMETRY_DATASET,
            market_code="pgh",
        )


async def ingest_pgh_sales(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    resource_id = str(config["sales_resource_id"])
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: pgh.load_pgh_sales(session, ckan, resource_id=resource_id),
            dataset=pgh.PGH_SALES_DATASET,
            market_code="pgh",
        )


async def ingest_pgh_liens(session_factory: SessionFactory, settings: Settings) -> int:
    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    resource_id = str(config["liens_resource_id"])
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: pgh.load_pgh_liens(session, ckan, resource_id=resource_id),
            dataset=pgh.PGH_LIENS_DATASET,
            market_code="pgh",
        )


async def ingest_pgh_foreclosures(session_factory: SessionFactory, settings: Settings) -> int:
    from datetime import UTC, datetime

    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    resource_id = str(config["foreclosures_resource_id"])
    as_of = datetime.now(UTC).date()
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: pgh.load_pgh_foreclosures(
                session, ckan, resource_id=resource_id, as_of=as_of
            ),
            dataset=pgh.PGH_FORECLOSURES_DATASET,
            market_code="pgh",
        )


async def _run_pgh_ckan(
    session_factory: SessionFactory,
    settings: Settings,
    *,
    resource_key: str,
    dataset: str,
    loader: Any,
) -> int:
    config = await _pgh_source_config(session_factory)
    base_url = str(config["ckan_base_url"])
    resource_id = str(config[resource_key])
    async with CkanDatastoreClient(settings, base_url) as ckan:
        return await run_loader(
            session_factory,
            lambda session: loader(session, ckan, resource_id=resource_id),
            dataset=dataset,
            market_code="pgh",
        )


async def ingest_pgh_violations(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_pgh_ckan(
        session_factory,
        settings,
        resource_key="violations_resource_id",
        dataset=pgh.PGH_VIOLATIONS_DATASET,
        loader=pgh.load_pgh_violations,
    )


async def ingest_pgh_city_owned(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_pgh_ckan(
        session_factory,
        settings,
        resource_key="city_owned_resource_id",
        dataset=pgh.PGH_CITY_OWNED_DATASET,
        loader=pgh.load_pgh_city_owned,
    )


async def ingest_pgh_condemned(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_pgh_ckan(
        session_factory,
        settings,
        resource_key="condemned_resource_id",
        dataset=pgh.PGH_CONDEMNED_DATASET,
        loader=pgh.load_pgh_condemned,
    )


async def ingest_pgh_zoning(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_pgh_ckan(
        session_factory,
        settings,
        resource_key="zoning_resource_id",
        dataset=pgh.PGH_ZONING_DATASET,
        loader=pgh.load_pgh_zoning_districts,
    )


async def ingest_pgh_neighborhoods(session_factory: SessionFactory, settings: Settings) -> int:
    return await _run_pgh_ckan(
        session_factory,
        settings,
        resource_key="neighborhoods_resource_id",
        dataset=pgh.PGH_NEIGHBORHOODS_DATASET,
        loader=pgh.load_pgh_neighborhoods,
    )


async def ingest_pgh_vacancy(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        pgh.derive_pgh_vacancy,
        dataset=pgh.PGH_VACANCY_DATASET,
        market_code="pgh",
    )


_PGH_JOBS: dict[str, Job] = {
    "parcels": ingest_pgh_parcels,
    "geometry": ingest_pgh_geometry,
    "sales": ingest_pgh_sales,
    "liens": ingest_pgh_liens,
    "foreclosures": ingest_pgh_foreclosures,
    "violations": ingest_pgh_violations,
    "city_owned": ingest_pgh_city_owned,
    "condemned": ingest_pgh_condemned,
    "zoning": ingest_pgh_zoning,
    "vacancy": ingest_pgh_vacancy,
    "neighborhoods": ingest_pgh_neighborhoods,
}


_HBG_JOBS: dict[str, Job] = {
    "parcels": ingest_hbg_parcels,
    "sales": ingest_hbg_sales,
    "zoning": ingest_hbg_zoning,
    "streets": ingest_hbg_streets,
    "historic": ingest_hbg_historic,
    "neighborhoods": ingest_hbg_neighborhoods,
    "vacancy": ingest_hbg_vacancy,
    "public": ingest_hbg_public,
    "repository": ingest_hbg_repository,
    "flood": ingest_hbg_flood,
    "dimensions": ingest_hbg_dimensions,
}

INGEST_JOBS: dict[tuple[str, str], Job] = {
    **{("phl", dataset): job for dataset, job in _PHL_JOBS.items()},
    **{("hbg", dataset): job for dataset, job in _HBG_JOBS.items()},
    **{("pgh", dataset): job for dataset, job in _PGH_JOBS.items()},
}

ParamJob = Callable[..., Awaitable[int]]

PARAM_INGEST_JOBS: dict[tuple[str, str], ParamJob] = {
    ("hbg", "tax_claim"): ingest_hbg_tax_claim,
}


def datasets_for_market(market: str) -> list[str]:
    return [dataset for (registered_market, dataset) in INGEST_JOBS if registered_market == market]


def markets() -> list[str]:
    return sorted({registered_market for (registered_market, _) in INGEST_JOBS})


async def ingest_market(
    session_factory: SessionFactory, settings: Settings, market: str = "phl"
) -> int:
    total = 0
    for dataset in datasets_for_market(market):
        total += await INGEST_JOBS[(market, dataset)](session_factory, settings)
    return total
