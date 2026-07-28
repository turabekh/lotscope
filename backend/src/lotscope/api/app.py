from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from lotscope.api.admin import router as admin_router
from lotscope.api.assemblage import router as assemblage_router
from lotscope.api.auth import router as auth_router
from lotscope.api.billing import router as billing_router
from lotscope.api.buyers import router as buyers_router
from lotscope.api.corrections import router as corrections_router
from lotscope.api.digests import router as digests_router
from lotscope.api.errors import register_exception_handlers
from lotscope.api.exports import router as exports_router
from lotscope.api.feed import router as feed_router
from lotscope.api.health import router as health_router
from lotscope.api.layers import router as layers_router
from lotscope.api.leads import router as leads_router
from lotscope.api.maps import router as maps_router
from lotscope.api.markets import router as markets_router
from lotscope.api.neighborhoods import router as neighborhoods_router
from lotscope.api.ops import router as ops_router
from lotscope.api.outreach import router as outreach_router
from lotscope.api.parcels import router as parcels_router
from lotscope.api.pipeline import router as pipeline_router
from lotscope.api.push import router as push_router
from lotscope.api.saved_searches import router as saved_searches_router
from lotscope.api.search import router as search_router
from lotscope.api.sheriff_sales import router as sheriff_sales_router
from lotscope.api.skiptrace import router as skiptrace_router
from lotscope.api.underwriting import router as underwriting_router
from lotscope.api.watchlist import router as watchlist_router
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        yield
    finally:
        await app.state.arq_pool.close()
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="LotScope PHL API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(billing_router)
    app.include_router(search_router)
    app.include_router(exports_router)
    app.include_router(buyers_router)
    app.include_router(parcels_router)
    app.include_router(layers_router)
    app.include_router(corrections_router)
    app.include_router(leads_router)
    app.include_router(markets_router)
    app.include_router(outreach_router)
    app.include_router(skiptrace_router)
    app.include_router(feed_router)
    app.include_router(sheriff_sales_router)
    app.include_router(assemblage_router)
    app.include_router(maps_router)
    app.include_router(watchlist_router)
    app.include_router(digests_router)
    app.include_router(push_router)
    app.include_router(pipeline_router)
    app.include_router(saved_searches_router)
    app.include_router(neighborhoods_router)
    app.include_router(admin_router)
    app.include_router(ops_router)
    app.include_router(underwriting_router)
    return app


app = create_app()
