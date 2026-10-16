from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tickers import Ticker
from app.repositories import PriceFilter, PriceRepository
from app.schemas import PriceSnapshot

pytestmark = pytest.mark.integration


@pytest.fixture
async def repository(session: AsyncSession) -> PriceRepository:
    repository = PriceRepository(session)
    for ticker, price, timestamp in [
        (Ticker.BTC_USD, "65000.12345678", 1_000),
        (Ticker.BTC_USD, "65100.5", 1_060),
        (Ticker.BTC_USD, "65200", 1_120),
        (Ticker.ETH_USD, "3100.01", 1_060),
    ]:
        await repository.add(
            PriceSnapshot(ticker=ticker, price=Decimal(price), timestamp=timestamp)
        )
    await session.commit()
    return repository


async def test_find_filters_by_ticker_newest_first(repository: PriceRepository) -> None:
    prices = await repository.find(PriceFilter(ticker=Ticker.BTC_USD), limit=10, offset=0)

    assert [p.timestamp for p in prices] == [1_120, 1_060, 1_000]
    assert {p.ticker for p in prices} == {"btc_usd"}


async def test_numeric_column_keeps_full_precision(repository: PriceRepository) -> None:
    prices = await repository.find(PriceFilter(ticker=Ticker.BTC_USD), limit=1, offset=2)

    assert prices[0].price == Decimal("65000.12345678")


async def test_find_and_count_apply_date_range(repository: PriceRepository) -> None:
    price_filter = PriceFilter(ticker=Ticker.BTC_USD, date_from=1_060, date_to=1_120)

    prices = await repository.find(price_filter, limit=10, offset=0)

    assert [p.timestamp for p in prices] == [1_120, 1_060]
    assert await repository.count(price_filter) == 2


async def test_find_paginates(repository: PriceRepository) -> None:
    page = await repository.find(PriceFilter(ticker=Ticker.BTC_USD), limit=1, offset=1)

    assert [p.timestamp for p in page] == [1_060]


async def test_get_latest(repository: PriceRepository) -> None:
    latest = await repository.get_latest(Ticker.ETH_USD)

    assert latest is not None
    assert (latest.price, latest.timestamp) == (Decimal("3100.01"), 1_060)


async def test_get_latest_without_data(session: AsyncSession) -> None:
    assert await PriceRepository(session).get_latest(Ticker.BTC_USD) is None
