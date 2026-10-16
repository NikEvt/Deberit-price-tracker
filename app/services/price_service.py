from collections.abc import Sequence
from typing import Protocol

from app.cache import LatestPriceCache
from app.core.exceptions import InvalidDateRangeError, PriceNotFoundError
from app.core.tickers import Ticker
from app.models import Price
from app.repositories import PriceFilter
from app.schemas import PricePage, PriceSnapshot


class PriceReader(Protocol):
    async def find(self, price_filter: PriceFilter, limit: int, offset: int) -> Sequence[Price]: ...

    async def count(self, price_filter: PriceFilter) -> int: ...

    async def get_latest(self, ticker: Ticker) -> Price | None: ...


class PriceService:
    def __init__(self, repository: PriceReader, cache: LatestPriceCache) -> None:
        self._repository = repository
        self._cache = cache

    async def get_all(self, ticker: Ticker, limit: int, offset: int) -> PricePage:
        return await self._get_page(PriceFilter(ticker=ticker), limit, offset)

    async def get_by_date(
        self,
        ticker: Ticker,
        date_from: int | None,
        date_to: int | None,
        limit: int,
        offset: int,
    ) -> PricePage:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidDateRangeError
        price_filter = PriceFilter(ticker=ticker, date_from=date_from, date_to=date_to)
        return await self._get_page(price_filter, limit, offset)

    async def get_latest(self, ticker: Ticker) -> PriceSnapshot:
        cached = await self._cache.get(ticker)
        if cached is not None:
            return cached

        price = await self._repository.get_latest(ticker)
        if price is None:
            raise PriceNotFoundError(ticker)
        return PriceSnapshot.model_validate(price)

    async def _get_page(self, price_filter: PriceFilter, limit: int, offset: int) -> PricePage:
        prices = await self._repository.find(price_filter, limit=limit, offset=offset)
        total = await self._repository.count(price_filter)
        return PricePage(
            items=[PriceSnapshot.model_validate(price) for price in prices],
            total=total,
            limit=limit,
            offset=offset,
        )
