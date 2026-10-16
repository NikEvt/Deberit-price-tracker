from decimal import Decimal

from sqlalchemy import BigInteger, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.money import PRICE_PRECISION, PRICE_SCALE
from app.db.base import Base


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (Index("ix_prices_ticker_timestamp", "ticker", "timestamp"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric(precision=PRICE_PRECISION, scale=PRICE_SCALE))
    timestamp: Mapped[int] = mapped_column(BigInteger)

    def __repr__(self) -> str:
        return f"Price(ticker={self.ticker!r}, price={self.price}, timestamp={self.timestamp})"
