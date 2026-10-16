import logging
from decimal import Decimal
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self

import aiohttp

from app.core.exceptions import PriceTrackerError
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot

logger = logging.getLogger(__name__)

MICROSECONDS_IN_SECOND = 1_000_000


class DeribitError(PriceTrackerError):
    """Base class for Deribit client errors."""


class DeribitUnavailableError(DeribitError):
    """Transient failure (network, timeout, 5xx). Safe to retry."""


class DeribitAPIError(DeribitError):
    """Deribit rejected the request or answered with something unexpected. Retrying won't help."""


class DeribitClient:
    """Async client for the public Deribit JSON-RPC over HTTP API.

    Owns its `aiohttp.ClientSession`; use as an async context manager:

        async with DeribitClient(base_url) as client:
            snapshot = await client.get_index_price(Ticker.BTC_USD)
    """

    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get_index_price(self, ticker: Ticker) -> PriceSnapshot:
        """Current index price of `ticker`, timestamped with Deribit's server time."""
        response = await self._call("public/get_index_price", {"index_name": ticker.value})
        try:
            price = Decimal(str(response["result"]["index_price"]))
            timestamp = int(response["usOut"]) // MICROSECONDS_IN_SECOND
        except (KeyError, TypeError, ArithmeticError, ValueError) as exc:
            raise DeribitAPIError(f"Unexpected response shape: {response!r}") from exc
        return PriceSnapshot(ticker=ticker, price=price, timestamp=timestamp)

    async def _call(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("DeribitClient must be used as an async context manager")

        url = f"{self._base_url}/{method}"
        try:
            async with self._session.get(url, params=params) as response:
                if response.status >= HTTPStatus.INTERNAL_SERVER_ERROR:
                    raise DeribitUnavailableError(f"Deribit returned HTTP {response.status}")
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DeribitUnavailableError(f"Request to {method} failed: {exc!r}") from exc
        except ValueError as exc:  # body is not JSON
            raise DeribitAPIError(f"Non-JSON response from {method}") from exc

        if not isinstance(payload, dict):
            raise DeribitAPIError(f"Unexpected response from {method}: {payload!r}")
        if "error" in payload:
            error = payload["error"]
            raise DeribitAPIError(f"Deribit error on {method}: {error!r}")

        logger.debug("Deribit %s(%s) -> %s", method, params, payload)
        return payload
