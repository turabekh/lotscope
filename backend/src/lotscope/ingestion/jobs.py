from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.ingestion.arcgis import ArcGisClient
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.filters import li_events_where, rtt_sales_where, zba_appeals_where
from lotscope.ingestion.loaders import (
    flood,
    historic,
    li,
    neighborhoods,
    opa,
    overlays,
    public_ownership,
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
from lotscope.zoning.overlay_membership import refresh_all_parcel_overlays

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
    total = await _run_arcgis(
        session_factory,
        settings,
        loader=overlays.load_zoning_overlays,
        dataset=overlays.ZONING_OVERLAY_DATASET,
    )
    async with session_factory() as session:
        await refresh_all_parcel_overlays(session)
        await session.commit()
    return total


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


async def ingest_derived_vacancy(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        vacancy.derive_phl_vacancy,
        dataset=vacancy.DERIVED_VACANCY_DATASET,
    )


async def ingest_public_ownership(session_factory: SessionFactory, settings: Settings) -> int:
    return await run_loader(
        session_factory,
        public_ownership.derive_phl_public_ownership,
        dataset=public_ownership.PUBLIC_OWNERSHIP_DATASET,
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
    "derived_vacancy": ingest_derived_vacancy,
    "public_ownership": ingest_public_ownership,
    "flood": ingest_flood,
    "neighborhoods": ingest_neighborhoods,
    "streets": ingest_streets,
    "historic": ingest_historic,
    "zba": ingest_zba,
}


INGEST_JOBS: dict[tuple[str, str], Job] = {
    (MARKET_CODE, dataset): job for dataset, job in _PHL_JOBS.items()
}

_logger = get_logger("ingestion.jobs")


def datasets_for_market(market: str) -> list[str]:
    return [dataset for (registered_market, dataset) in INGEST_JOBS if registered_market == market]


def markets() -> list[str]:
    return sorted({registered_market for (registered_market, _) in INGEST_JOBS})


async def ingest_market(
    session_factory: SessionFactory, settings: Settings, market: str = MARKET_CODE
) -> int:
    total = 0
    failed: list[str] = []
    for dataset in datasets_for_market(market):
        try:
            total += await INGEST_JOBS[(market, dataset)](session_factory, settings)
        except CancelledError:
            raise
        except Exception as exc:
            failed.append(dataset)
            _logger.error("dataset_ingest_failed", market=market, dataset=dataset, error=str(exc))
    if failed:
        raise IngestionError(
            f"{len(failed)} of {len(datasets_for_market(market))} {market} dataset(s) failed: "
            + ", ".join(failed)
        )
    return total
