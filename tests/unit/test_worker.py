from decimal import Decimal

import pytest

from app.clients import DeribitUnavailableError
from app.core.config import Settings
from app.core.tickers import Ticker
from app.schemas import PriceSnapshot
from app.worker import tasks
from app.worker.celery_app import COLLECT_PRICE_TASK, PriceTrackerCelery, create_celery_app


@pytest.fixture
def celery_app() -> PriceTrackerCelery:
    app = create_celery_app(Settings(collect_interval_seconds=60, tickers=list(Ticker)))
    app.conf.task_always_eager = True
    return app


def test_beat_schedules_every_ticker_each_interval(celery_app: PriceTrackerCelery) -> None:
    schedule = celery_app.conf.beat_schedule

    assert set(schedule) == {"collect-btc_usd", "collect-eth_usd"}
    entry = schedule["collect-btc_usd"]
    assert entry["task"] == COLLECT_PRICE_TASK
    assert entry["schedule"] == 60.0
    assert entry["args"] == ("btc_usd",)
    assert entry["options"] == {"expires": 60}


def test_task_retries_only_transient_errors(celery_app: PriceTrackerCelery) -> None:
    task = celery_app.tasks[COLLECT_PRICE_TASK]

    assert task.autoretry_for == (DeribitUnavailableError,)
    assert task.max_retries == 3


def test_task_runs_collection_with_app_settings(
    celery_app: PriceTrackerCelery, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Settings, Ticker]] = []

    async def fake_collect(settings: Settings, ticker: Ticker) -> PriceSnapshot:
        calls.append((settings, ticker))
        return PriceSnapshot(ticker=ticker, price=Decimal("1.5"), timestamp=42)

    monkeypatch.setattr(tasks, "collect_and_store", fake_collect)

    result = celery_app.tasks[COLLECT_PRICE_TASK].apply(args=("eth_usd",)).get()

    assert calls == [(celery_app.settings, Ticker.ETH_USD)]
    assert result == {"ticker": "eth_usd", "price": "1.50000000", "timestamp": 42}
