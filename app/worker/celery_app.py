from typing import Any

from celery import Celery

from app.core.config import Settings

COLLECT_PRICE_TASK = "prices.collect_index_price"


class PriceTrackerCelery(Celery):  # type: ignore[misc]
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            "price_tracker",
            broker=settings.celery_broker_url,
            include=["app.worker.tasks"],
        )
        self.settings = settings
        self.conf.update(
            beat_schedule=build_beat_schedule(settings),
            broker_connection_retry_on_startup=True,
            task_ignore_result=True,
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            timezone="UTC",
            worker_enable_remote_control=False,
        )


def build_beat_schedule(settings: Settings) -> dict[str, dict[str, Any]]:
    return {
        f"collect-{ticker.value}": {
            "task": COLLECT_PRICE_TASK,
            "schedule": float(settings.collect_interval_seconds),
            "args": (ticker.value,),
            "options": {"expires": settings.collect_interval_seconds},
        }
        for ticker in settings.tickers
    }


def create_celery_app(settings: Settings) -> PriceTrackerCelery:
    return PriceTrackerCelery(settings)
