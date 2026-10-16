from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_price_service
from app.core.config import Settings
from app.core.tickers import Ticker
from app.main import create_app
from app.services import PriceService
from tests.fakes import InMemoryLatestPriceCache, InMemoryPriceRepository, make_price


@pytest.fixture
def repository() -> InMemoryPriceRepository:
    return InMemoryPriceRepository(
        [
            make_price(Ticker.BTC_USD, "65000.5", 1_000),
            make_price(Ticker.BTC_USD, "65100.25", 1_060),
            make_price(Ticker.ETH_USD, "3100", 1_060),
        ]
    )


@pytest.fixture
def app(repository: InMemoryPriceRepository) -> FastAPI:
    application = create_app(Settings(redis_url=None))
    service = PriceService(repository, InMemoryLatestPriceCache())
    application.dependency_overrides[get_price_service] = lambda: service
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def test_get_all_prices(client: AsyncClient) -> None:
    response = await client.get("/api/v1/prices", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"ticker": "btc_usd", "price": "65100.25000000", "timestamp": 1_060},
            {"ticker": "btc_usd", "price": "65000.50000000", "timestamp": 1_000},
        ],
        "total": 2,
        "limit": 100,
        "offset": 0,
    }


async def test_get_latest_price(client: AsyncClient) -> None:
    response = await client.get("/api/v1/prices/latest", params={"ticker": "eth_usd"})

    assert response.status_code == 200
    assert response.json() == {"ticker": "eth_usd", "price": "3100.00000000", "timestamp": 1_060}


async def test_get_latest_price_404_when_empty(
    repository: InMemoryPriceRepository, client: AsyncClient
) -> None:
    repository.prices.clear()

    response = await client.get("/api/v1/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 404
    assert "btc_usd" in response.json()["detail"]


async def test_get_prices_by_date(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/prices/by-date",
        params={"ticker": "btc_usd", "date_from": 1_030, "date_to": 2_000},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["timestamp"] == 1_060


async def test_get_prices_by_date_rejects_inverted_range(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/prices/by-date", params={"ticker": "btc_usd", "date_from": 10, "date_to": 5}
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path", ["/api/v1/prices", "/api/v1/prices/latest", "/api/v1/prices/by-date"]
)
async def test_ticker_is_required(client: AsyncClient, path: str) -> None:
    response = await client.get(path)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "ticker"]


@pytest.mark.parametrize(
    "path", ["/api/v1/prices", "/api/v1/prices/latest", "/api/v1/prices/by-date"]
)
async def test_unknown_ticker_is_rejected(client: AsyncClient, path: str) -> None:
    response = await client.get(path, params={"ticker": "doge_usd"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 1001}, {"offset": -1}],
)
async def test_pagination_bounds(client: AsyncClient, params: dict[str, int]) -> None:
    response = await client.get("/api/v1/prices", params={"ticker": "btc_usd", **params})

    assert response.status_code == 422


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_metrics_are_exposed(client: AsyncClient) -> None:
    await client.get("/health")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
