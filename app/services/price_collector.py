import logging
from typing import Protocol

from app.core.tickers import Ticker
from app.schemas import PriceSnapshot

logger = logging.getLogger(__name__)


class PriceProvider(Protocol):
    async def get_index_price(self, ticker: Ticker) -> PriceSnapshot: ...


class PriceWriter(Protocol):
    async def add(self, snapshot: PriceSnapshot) -> None: ...


class PriceCollector:
    def __init__(self, provider: PriceProvider, repository: PriceWriter) -> None:
        self._provider = provider
        self._repository = repository

    async def collect(self, ticker: Ticker) -> PriceSnapshot:
        snapshot = await self._provider.get_index_price(ticker)
        await self._repository.add(snapshot)
        logger.info("Collected %s = %s at %d", snapshot.ticker, snapshot.price, snapshot.timestamp)
        return snapshot
