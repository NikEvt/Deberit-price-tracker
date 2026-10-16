from decimal import Decimal

import pytest

from app.clients import DeribitUnavailableError
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot
from app.services import PriceCollector
from tests.fakes import InMemoryPriceRepository, StubPriceProvider

SNAPSHOT = PriceSnapshot(ticker=Ticker.ETH_USD, price=Decimal("3100.12"), timestamp=1_700_000_000)


async def test_collect_fetches_and_stores_price() -> None:
    provider = StubPriceProvider(snapshot=SNAPSHOT)
    repository = InMemoryPriceRepository()

    result = await PriceCollector(provider, repository).collect(Ticker.ETH_USD)

    assert result == SNAPSHOT
    assert provider.requested == [Ticker.ETH_USD]
    assert len(repository.prices) == 1
    stored = repository.prices[0]
    assert (stored.ticker, stored.price, stored.timestamp) == (
        "eth_usd",
        SNAPSHOT.price,
        1_700_000_000,
    )


async def test_collect_stores_nothing_when_provider_fails() -> None:
    provider = StubPriceProvider(error=DeribitUnavailableError("timeout"))
    repository = InMemoryPriceRepository()

    with pytest.raises(DeribitUnavailableError):
        await PriceCollector(provider, repository).collect(Ticker.ETH_USD)

    assert repository.prices == []
