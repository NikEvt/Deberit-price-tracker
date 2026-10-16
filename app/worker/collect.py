from sqlalchemy.pool import NullPool

from app.cache import latest_price_cache
from app.clients import DeribitClient
from app.core.config import Settings
from app.core.tickers import Ticker
from app.db.session import create_engine, create_session_factory
from app.repositories import PriceRepository
from app.schemas import PriceSnapshot
from app.services import PriceCollector


async def collect_and_store(settings: Settings, ticker: Ticker) -> PriceSnapshot:
    engine = create_engine(settings, poolclass=NullPool)
    session_factory = create_session_factory(engine)
    try:
        async with (
            DeribitClient(settings.deribit_base_url, settings.deribit_timeout_seconds) as client,
            session_factory.begin() as session,
        ):
            collector = PriceCollector(provider=client, repository=PriceRepository(session))
            snapshot = await collector.collect(ticker)
        async with latest_price_cache(settings) as cache:
            await cache.set(snapshot)
        return snapshot
    finally:
        await engine.dispose()
