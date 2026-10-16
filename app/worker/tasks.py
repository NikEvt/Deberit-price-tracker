import asyncio
from typing import Any

from celery import Task, shared_task

from app.clients import DeribitUnavailableError
from app.core.tickers import Ticker
from app.worker.celery_app import COLLECT_PRICE_TASK, PriceTrackerCelery
from app.worker.collect import collect_and_store


@shared_task(
    bind=True,
    name=COLLECT_PRICE_TASK,
    autoretry_for=(DeribitUnavailableError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def collect_index_price(self: Task, ticker: str) -> dict[str, Any]:
    app = self.app
    if not isinstance(app, PriceTrackerCelery):
        raise TypeError("collect_index_price must run in a PriceTrackerCelery app")

    snapshot = asyncio.run(collect_and_store(app.settings, Ticker(ticker)))
    return snapshot.model_dump(mode="json")
