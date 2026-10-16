from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import InvalidDateRangeError, PriceNotFoundError


async def _price_not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=HTTPStatus.NOT_FOUND, content={"detail": str(exc)})


async def _invalid_date_range(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PriceNotFoundError, _price_not_found)
    app.add_exception_handler(InvalidDateRangeError, _invalid_date_range)
