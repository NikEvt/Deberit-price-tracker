from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import quantize_price
from app.core.tickers import Ticker


class PriceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    ticker: Ticker
    price: Decimal = Field(description="Index price. Serialized as a string to keep precision.")
    timestamp: int = Field(description="UNIX timestamp in seconds (UTC)")

    @field_validator("price")
    @classmethod
    def _quantize(cls, value: Decimal) -> Decimal:
        return quantize_price(value)


class PricePage(BaseModel):
    items: list[PriceSnapshot]
    total: int = Field(description="Number of records matching the filter")
    limit: int
    offset: int
