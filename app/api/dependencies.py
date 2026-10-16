from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache import LatestPriceCache
from app.repositories import PriceRepository
from app.services import PriceService


@dataclass(frozen=True, slots=True)
class AppResources:
    session_factory: async_sessionmaker[AsyncSession]
    price_cache: LatestPriceCache


def get_resources(request: Request) -> AppResources:
    resources: AppResources = request.app.state.resources
    return resources


async def get_session(
    resources: Annotated[AppResources, Depends(get_resources)],
) -> AsyncIterator[AsyncSession]:
    async with resources.session_factory() as session:
        yield session


def get_price_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    resources: Annotated[AppResources, Depends(get_resources)],
) -> PriceService:
    return PriceService(PriceRepository(session), resources.price_cache)


PriceServiceDep = Annotated[PriceService, Depends(get_price_service)]
