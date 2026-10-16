from decimal import Decimal

from app.core.tickers import Ticker
from app.schemas import PriceSnapshot
from tests.fakes import make_price


def test_price_is_quantized_to_database_scale() -> None:
    snapshot = PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal("82153.67"), timestamp=1)

    assert snapshot.model_dump(mode="json")["price"] == "82153.67000000"


def test_fresh_and_stored_prices_serialize_identically() -> None:
    fresh = PriceSnapshot(ticker=Ticker.BTC_USD, price=Decimal("82153.67"), timestamp=1)
    stored = PriceSnapshot.model_validate(make_price(Ticker.BTC_USD, "82153.67000000", 1))

    assert fresh.model_dump_json() == stored.model_dump_json()
