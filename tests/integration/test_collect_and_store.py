from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.tickers import Ticker
from app.repositories import PriceFilter, PriceRepository
from app.worker.collect import collect_and_store

pytestmark = pytest.mark.integration


@pytest.fixture
async def deribit_url() -> AsyncIterator[str]:
    async def index_price(request: web.Request) -> web.Response:
        assert request.query["index_name"] == "eth_usd"
        return web.json_response(
            {"result": {"index_price": 3123.45}, "usOut": 1_792_133_371_952_301}
        )

    app = web.Application()
    app.router.add_get("/api/v2/public/get_index_price", index_price)
    async with TestServer(app) as server:
        yield str(server.make_url("/api/v2"))


async def test_collect_and_store_persists_price(
    settings: Settings, deribit_url: str, session: AsyncSession
) -> None:
    worker_settings = settings.model_copy(update={"deribit_base_url": deribit_url})

    snapshot = await collect_and_store(worker_settings, Ticker.ETH_USD)

    stored = await PriceRepository(session).find(
        PriceFilter(ticker=Ticker.ETH_USD), limit=10, offset=0
    )
    assert len(stored) == 1
    assert (stored[0].price, stored[0].timestamp) == (Decimal("3123.45"), 1_792_133_371)
    assert snapshot.price == Decimal("3123.45")
