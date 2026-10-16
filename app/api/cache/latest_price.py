import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot

logger = logging.getLogger(__name__)


class LatestPriceCache(Protocol):
    async def get(self, ticker: Ticker) -> PriceSnapshot | None: ...

    async def set(self, snapshot: PriceSnapshot) -> None: ...


class NullLatestPriceCache:

    async def get(self, ticker: Ticker) -> PriceSnapshot | None:
        return None

    async def set(self, snapshot: PriceSnapshot) -> None:
        return None


class RedisLatestPriceCache:

    KEY_PREFIX = "prices:latest:"

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    async def get(self, ticker: Ticker) -> PriceSnapshot | None:
        try:
            raw = await self._redis.get(self._key(ticker))
        except RedisError:
            logger.warning("Redis unavailable, reading latest %s from the database", ticker)
            return None
        if raw is None:
            return None
        try:
            return PriceSnapshot.model_validate_json(raw)
        except ValidationError:
            logger.warning("Corrupted cache entry for %s, ignoring it", ticker)
            return None

    async def set(self, snapshot: PriceSnapshot) -> None:
        try:
            await self._redis.set(
                self._key(snapshot.ticker), snapshot.model_dump_json(), ex=self._ttl_seconds
            )
        except RedisError:
            logger.warning("Failed to cache latest %s price", snapshot.ticker)

    def _key(self, ticker: Ticker) -> str:
        return f"{self.KEY_PREFIX}{ticker.value}"


@asynccontextmanager
async def latest_price_cache(settings: Settings) -> AsyncIterator[LatestPriceCache]:
    
    if settings.redis_url is None:
        yield NullLatestPriceCache()
        return

    redis = Redis.from_url(settings.redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
    try:
        yield RedisLatestPriceCache(redis, ttl_seconds=settings.latest_price_cache_ttl_seconds)
    finally:
        await redis.aclose()
