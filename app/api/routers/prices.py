from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.dependencies import PriceServiceDep
from app.core.tickers import Ticker
from app.schemas import PricePage, PriceSnapshot

router = APIRouter(prefix="/prices", tags=["prices"])

TickerQuery = Annotated[Ticker, Query(description="Currency ticker")]
LimitQuery = Annotated[int, Query(ge=1, le=1000, description="Page size")]
OffsetQuery = Annotated[int, Query(ge=0, description="Number of records to skip")]
TimestampQuery = Annotated[
    int | None, Query(ge=0, description="Inclusive bound, UNIX timestamp in seconds")
]

NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {"description": "No prices stored for the ticker yet"}
}


@router.get("", summary="All stored prices of a currency, newest first")
async def get_all_prices(
    service: PriceServiceDep,
    ticker: TickerQuery,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> PricePage:
    return await service.get_all(ticker, limit=limit, offset=offset)


@router.get("/latest", summary="Latest price of a currency", responses=NOT_FOUND_RESPONSE)
async def get_latest_price(service: PriceServiceDep, ticker: TickerQuery) -> PriceSnapshot:
    return await service.get_latest(ticker)


@router.get("/by-date", summary="Prices of a currency within a time range, newest first")
async def get_prices_by_date(
    service: PriceServiceDep,
    ticker: TickerQuery,
    date_from: TimestampQuery = None,
    date_to: TimestampQuery = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> PricePage:
    return await service.get_by_date(
        ticker, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
