from decimal import Decimal
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError

from app.cache import NullLatestPriceCache, RedisLatestPriceCache, latest_price_cache
from app.core.config import Settings
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot

SNAPSHOT = PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal("65000.12345678"), timestamp=1)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.store[key] = value
        self.ttls[key] = ex


class BrokenRedis:
    async def get(self, *args: Any, **kwargs: Any) -> None:
        raise RedisConnectionError("down")

    async def set(self, *args: Any, **kwargs: Any) -> None:
        raise RedisConnectionError("down")


async def test_round_trip_keeps_decimal_precision_and_sets_ttl() -> None:
    redis = FakeRedis()
    cache = RedisLatestPriceCache(redis, ttl_seconds=120)  # type: ignore[arg-type]

    await cache.set(SNAPSHOT)

    assert await cache.get(Ticker.BTC_USD) == SNAPSHOT
    assert await cache.get(Ticker.ETH_USD) is None
    assert redis.ttls == {"prices:latest:btc_usd": 120}


async def test_redis_failure_is_a_miss_not_an_error() -> None:
    cache = RedisLatestPriceCache(BrokenRedis(), ttl_seconds=120)  # type: ignore[arg-type]

    await cache.set(SNAPSHOT)
    assert await cache.get(Ticker.BTC_USD) is None


async def test_corrupted_entry_is_ignored() -> None:
    redis = FakeRedis()
    redis.store["prices:latest:btc_usd"] = "{not json"
    cache = RedisLatestPriceCache(redis, ttl_seconds=120)  # type: ignore[arg-type]

    assert await cache.get(Ticker.BTC_USD) is None


async def test_without_redis_url_cache_is_disabled() -> None:
    async with latest_price_cache(Settings(redis_url=None)) as cache:
        assert isinstance(cache, NullLatestPriceCache)
        await cache.set(SNAPSHOT)
        assert await cache.get(Ticker.BTC_USD) is None
