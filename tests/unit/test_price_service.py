from decimal import Decimal

import pytest

from app.core.exceptions import InvalidDateRangeError, PriceNotFoundError
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot
from app.services import PriceService
from tests.fakes import InMemoryLatestPriceCache, InMemoryPriceRepository, make_price


@pytest.fixture
def repository() -> InMemoryPriceRepository:
    return InMemoryPriceRepository(
        [
            make_price(Ticker.BTC_USD, "100.5", 1_000),
            make_price(Ticker.BTC_USD, "101.5", 1_060),
            make_price(Ticker.BTC_USD, "102.5", 1_120),
            make_price(Ticker.ETH_USD, "5.25", 1_060),
        ]
    )


@pytest.fixture
def cache() -> InMemoryLatestPriceCache:
    return InMemoryLatestPriceCache()


@pytest.fixture
def service(repository: InMemoryPriceRepository, cache: InMemoryLatestPriceCache) -> PriceService:
    return PriceService(repository, cache)


async def test_get_all_returns_only_requested_ticker_newest_first(service: PriceService) -> None:
    page = await service.get_all(Ticker.BTC_USD, limit=10, offset=0)

    assert page.total == 3
    assert [item.timestamp for item in page.items] == [1_120, 1_060, 1_000]
    assert {item.ticker for item in page.items} == {Ticker.BTC_USD}


async def test_get_all_paginates(service: PriceService) -> None:
    page = await service.get_all(Ticker.BTC_USD, limit=2, offset=1)

    assert page.total == 3
    assert [item.timestamp for item in page.items] == [1_060, 1_000]
    assert (page.limit, page.offset) == (2, 1)


async def test_get_by_date_applies_inclusive_bounds(service: PriceService) -> None:
    page = await service.get_by_date(
        Ticker.BTC_USD, date_from=1_060, date_to=1_120, limit=10, offset=0
    )

    assert page.total == 2
    assert [item.price for item in page.items] == [Decimal("102.5"), Decimal("101.5")]


async def test_get_by_date_with_open_bound(service: PriceService) -> None:
    page = await service.get_by_date(
        Ticker.BTC_USD, date_from=None, date_to=1_060, limit=10, offset=0
    )

    assert [item.timestamp for item in page.items] == [1_060, 1_000]


async def test_get_by_date_rejects_inverted_range(service: PriceService) -> None:
    with pytest.raises(InvalidDateRangeError):
        await service.get_by_date(Ticker.BTC_USD, date_from=2, date_to=1, limit=10, offset=0)


async def test_get_latest_reads_database_on_cache_miss(service: PriceService) -> None:
    latest = await service.get_latest(Ticker.BTC_USD)

    assert latest == PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal("102.5"), timestamp=1_120)


async def test_get_latest_prefers_cache(
    service: PriceService, cache: InMemoryLatestPriceCache
) -> None:
    cached = PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal("200"), timestamp=2_000)
    await cache.set(cached)

    assert await service.get_latest(Ticker.BTC_USD) == cached


async def test_get_latest_raises_when_nothing_stored(cache: InMemoryLatestPriceCache) -> None:
    service = PriceService(InMemoryPriceRepository(), cache)

    with pytest.raises(PriceNotFoundError):
        await service.get_latest(Ticker.ETH_USD)
