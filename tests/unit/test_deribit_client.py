import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from app.clients import DeribitAPIError, DeribitClient, DeribitUnavailableError
from app.core.tickers import Ticker

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]

INDEX_PRICE_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {"estimated_delivery_price": 82153.67, "index_price": 82153.67},
    "usIn": 1792133371951978,
    "usOut": 1792133371952301,
    "usDiff": 323,
    "testnet": False,
}


class FakeDeribit:
    def __init__(self) -> None:
        self.handler: Handler = self._unconfigured
        self.queries: list[dict[str, str]] = []

    async def dispatch(self, request: web.Request) -> web.StreamResponse:
        self.queries.append(dict(request.query))
        return await self.handler(request)

    @staticmethod
    async def _unconfigured(request: web.Request) -> web.StreamResponse:
        raise AssertionError("FakeDeribit.handler is not configured")


@pytest.fixture
async def deribit() -> AsyncIterator[tuple[FakeDeribit, str]]:
    fake = FakeDeribit()
    app = web.Application()
    app.router.add_get("/api/v2/public/get_index_price", fake.dispatch)
    async with TestServer(app) as server:
        yield fake, str(server.make_url("/api/v2"))


def respond_json(payload: object, status: int = 200) -> Handler:
    async def handler(request: web.Request) -> web.StreamResponse:
        return web.json_response(payload, status=status)

    return handler


def respond_text(text: str, status: int = 200) -> Handler:
    async def handler(request: web.Request) -> web.StreamResponse:
        return web.Response(text=text, status=status)

    return handler


async def test_get_index_price_parses_price_and_server_time(
    deribit: tuple[FakeDeribit, str],
) -> None:
    fake, base_url = deribit
    fake.handler = respond_json(INDEX_PRICE_RESPONSE)

    async with DeribitClient(base_url) as client:
        snapshot = await client.get_index_price(Ticker.BTC_USD)

    assert fake.queries == [{"index_name": "btc_usd"}]
    assert snapshot.ticker is Ticker.BTC_USD
    assert snapshot.price == Decimal("82153.67")
    assert snapshot.timestamp == 1792133371


async def test_api_error_is_not_retryable(deribit: tuple[FakeDeribit, str]) -> None:
    fake, base_url = deribit
    fake.handler = respond_json(
        {"jsonrpc": "2.0", "error": {"code": 10004, "message": "Invalid params"}}, status=400
    )

    async with DeribitClient(base_url) as client:
        with pytest.raises(DeribitAPIError, match="Invalid params"):
            await client.get_index_price(Ticker.BTC_USD)


async def test_server_error_is_retryable(deribit: tuple[FakeDeribit, str]) -> None:
    fake, base_url = deribit
    fake.handler = respond_text("Service Unavailable", status=503)

    async with DeribitClient(base_url) as client:
        with pytest.raises(DeribitUnavailableError, match="503"):
            await client.get_index_price(Ticker.BTC_USD)


async def test_timeout_is_retryable(deribit: tuple[FakeDeribit, str]) -> None:
    fake, base_url = deribit

    async def slow(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(1)
        return web.json_response(INDEX_PRICE_RESPONSE)

    fake.handler = slow

    async with DeribitClient(base_url, timeout_seconds=0.05) as client:
        with pytest.raises(DeribitUnavailableError):
            await client.get_index_price(Ticker.BTC_USD)


async def test_connection_failure_is_retryable() -> None:
    async with DeribitClient("http://127.0.0.1:1/api/v2") as client:
        with pytest.raises(DeribitUnavailableError):
            await client.get_index_price(Ticker.BTC_USD)


@pytest.mark.parametrize(
    "handler",
    [
        respond_json({"result": {}, "usOut": 1}),
        respond_json({"result": {"index_price": 1.0}}),
        respond_json({"result": {"index_price": "abc"}, "usOut": 1}),
        respond_json(["not", "an", "object"]),
        respond_text("<html>not json</html>"),
    ],
    ids=["no-price", "no-time", "bad-price", "not-object", "not-json"],
)
async def test_unexpected_response_raises_api_error(
    deribit: tuple[FakeDeribit, str], handler: Handler
) -> None:
    fake, base_url = deribit
    fake.handler = handler

    async with DeribitClient(base_url) as client:
        with pytest.raises(DeribitAPIError):
            await client.get_index_price(Ticker.BTC_USD)


async def test_client_requires_context_manager() -> None:
    with pytest.raises(RuntimeError, match="context manager"):
        await DeribitClient("http://unused").get_index_price(Ticker.BTC_USD)
