from collections.abc import Sequence
from decimal import Decimal

from app.core.tickers import Ticker
from app.models import Price
from app.repositories import PriceFilter
from app.schemas import PriceSnapshot


def make_price(ticker: Ticker, price: str, timestamp: int) -> Price:
    return Price(ticker=ticker.value, price=Decimal(price), timestamp=timestamp)


class InMemoryPriceRepository:
    def __init__(self, prices: Sequence[Price] = ()) -> None:
        self.prices = list(prices)

    async def add(self, snapshot: PriceSnapshot) -> None:
        self.prices.append(
            Price(ticker=snapshot.ticker.value, price=snapshot.price, timestamp=snapshot.timestamp)
        )

    async def find(self, price_filter: PriceFilter, limit: int, offset: int) -> Sequence[Price]:
        matching = sorted(self._matching(price_filter), key=lambda p: p.timestamp, reverse=True)
        return matching[offset : offset + limit]

    async def count(self, price_filter: PriceFilter) -> int:
        return len(self._matching(price_filter))

    async def get_latest(self, ticker: Ticker) -> Price | None:
        return max(
            self._matching(PriceFilter(ticker=ticker)), key=lambda p: p.timestamp, default=None
        )

    def _matching(self, price_filter: PriceFilter) -> list[Price]:
        return [
            price
            for price in self.prices
            if price.ticker == price_filter.ticker.value
            and (price_filter.date_from is None or price.timestamp >= price_filter.date_from)
            and (price_filter.date_to is None or price.timestamp <= price_filter.date_to)
        ]


class InMemoryLatestPriceCache:
    def __init__(self) -> None:
        self.entries: dict[Ticker, PriceSnapshot] = {}

    async def get(self, ticker: Ticker) -> PriceSnapshot | None:
        return self.entries.get(ticker)

    async def set(self, snapshot: PriceSnapshot) -> None:
        self.entries[snapshot.ticker] = snapshot


class StubPriceProvider:
    def __init__(self, snapshot: PriceSnapshot | None = None, error: Exception | None = None):
        self._snapshot = snapshot
        self._error = error
        self.requested: list[Ticker] = []

    async def get_index_price(self, ticker: Ticker) -> PriceSnapshot:
        self.requested.append(ticker)
        if self._error is not None:
            raise self._error
        assert self._snapshot is not None
        return self._snapshot
