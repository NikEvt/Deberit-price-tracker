from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.dependencies import AppResources
from app.api.errors import register_exception_handlers
from app.api.routers import health, prices
from app.cache import latest_price_cache
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def build_lifespan(settings: Settings) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        try:
            async with latest_price_cache(settings) as cache:
                app.state.resources = AppResources(
                    session_factory=create_session_factory(engine),
                    price_cache=cache,
                )
                yield
        finally:
            await engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Deribit Price Tracker",
        version="1.0.0",
        description="Index prices of BTC and ETH collected from Deribit every minute.",
        lifespan=build_lifespan(settings),
    )
    app.include_router(prices.router, prefix="/api/v1")
    app.include_router(health.router)
    register_exception_handlers(app)
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    return app
