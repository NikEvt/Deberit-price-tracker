from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tickers import Ticker
from app.models import Price
from app.schemas import PriceSnapshot


@dataclass(frozen=True, slots=True)
class PriceFilter:
    ticker: Ticker
    date_from: int | None = None
    date_to: int | None = None

    def to_conditions(self) -> list[ColumnElement[bool]]:
        conditions = [Price.ticker == self.ticker.value]
        if self.date_from is not None:
            conditions.append(Price.timestamp >= self.date_from)
        if self.date_to is not None:
            conditions.append(Price.timestamp <= self.date_to)
        return conditions


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, snapshot: PriceSnapshot) -> None:
        await self._session.execute(
            insert(Price).values(
                ticker=snapshot.ticker.value,
                price=snapshot.price,
                timestamp=snapshot.timestamp,
            )
        )

    async def find(self, price_filter: PriceFilter, limit: int, offset: int) -> Sequence[Price]:
        query = (
            select(Price)
            .where(*price_filter.to_conditions())
            .order_by(Price.timestamp.desc(), Price.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.scalars(query)
        return result.all()

    async def count(self, price_filter: PriceFilter) -> int:
        query = select(func.count()).select_from(Price).where(*price_filter.to_conditions())
        return (await self._session.scalar(query)) or 0

    async def get_latest(self, ticker: Ticker) -> Price | None:
        query = (
            select(Price)
            .where(Price.ticker == ticker.value)
            .order_by(Price.timestamp.desc(), Price.id.desc())
            .limit(1)
        )
        return await self._session.scalar(query)
