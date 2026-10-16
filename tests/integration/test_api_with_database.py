from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.tickers import Ticker
from app.main import create_app
from app.repositories import PriceRepository
from app.schemas import PriceSnapshot

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(settings: Settings, session: AsyncSession) -> AsyncIterator[AsyncClient]:
    repository = PriceRepository(session)
    for price, timestamp in [("65000.5", 1_000), ("65100.25", 1_060)]:
        await repository.add(
            PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal(price), timestamp=timestamp)
        )
    await session.commit()

    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


async def test_endpoints_read_from_postgres(client: AsyncClient) -> None:
    latest = await client.get("/api/v1/prices/latest", params={"ticker": "btc_usd"})
    by_date = await client.get(
        "/api/v1/prices/by-date", params={"ticker": "btc_usd", "date_to": 1_030}
    )
    everything = await client.get("/api/v1/prices", params={"ticker": "btc_usd"})

    assert latest.json() == {"ticker": "btc_usd", "price": "65100.25000000", "timestamp": 1_060}
    assert [item["timestamp"] for item in by_date.json()["items"]] == [1_000]
    assert everything.json()["total"] == 2
