# Deribit Price Tracker

Сервис раз в минуту забирает с биржи [Deribit](https://docs.deribit.com/) index price `btc_usd` и `eth_usd`, сохраняет в PostgreSQL тикер, цену и время (UNIX timestamp) и отдаёт данные через API на FastAPI.

**Стек:** Python 3.12, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16, Alembic, Celery + RabbitMQ, Redis, aiohttp, Docker Compose, pytest.

## Запуск

Нужен Docker с Compose v2.

```bash
git clone <repo-url> deribit-price-tracker
cd deribit-price-tracker
docker compose up -d --build
```

Compose поднимает PostgreSQL, RabbitMQ и Redis, применяет миграции и запускает `api`, `worker` и `beat`. Первые цены появляются примерно через минуту:

```bash
docker compose logs -f worker   # Collected btc_usd = 81860.39000000 at 1792156643
curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
```

- Swagger UI: <http://localhost:8000/docs>
- Prometheus (опционально): `docker compose --profile monitoring up -d`, затем <http://localhost:9090>
- Остановить: `docker compose down`, вместе с данными: `docker compose down -v`

## API

Все методы `GET`, у каждого обязательный параметр `ticker` (`btc_usd` или `eth_usd`). Без тикера или с неизвестным тикером API отвечает `422`.

| Метод | Описание | Параметры |
|---|---|---|
| `/api/v1/prices` | Все цены валюты, сначала новые | `limit` (1–1000, по умолчанию 100), `offset` |
| `/api/v1/prices/latest` | Последняя цена (`404`, если данных нет) | — |
| `/api/v1/prices/by-date` | Цены за интервал | `date_from`, `date_to` (UNIX timestamp, включительно, обе необязательны), `limit`, `offset` |
| `/health`, `/metrics` | Liveness-проба и метрики Prometheus | — |

```bash
$ curl "http://localhost:8000/api/v1/prices/latest?ticker=btc_usd"
{"ticker":"btc_usd","price":"81860.39000000","timestamp":1792156643}

$ curl "http://localhost:8000/api/v1/prices/by-date?ticker=eth_usd&date_from=1792156000&limit=2"
{"items":[{"ticker":"eth_usd","price":"2459.79000000","timestamp":1792156643}],"total":1,"limit":2,"offset":0}
```

## Локальная разработка

Нужен [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres rabbitmq redis

uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
uv run celery -A app.worker.main worker -l INFO --without-mingle --without-gossip
uv run celery -A app.worker.main beat -l INFO
```

## Тесты

```bash
uv run pytest tests/unit   # unit-тесты, внешние сервисы не нужны

# вместе с интеграционными на PostgreSQL (база будет очищена)
docker run -d --rm --name prices-test-db -p 55432:5432 \
  -e POSTGRES_USER=prices -e POSTGRES_PASSWORD=prices -e POSTGRES_DB=prices_test postgres:16-alpine
TEST_DATABASE_URL=postgresql+asyncpg://prices:prices@localhost:55432/prices_test uv run pytest --cov
```

46 unit-тестов и 8 интеграционных, покрытие 98 %. Без `TEST_DATABASE_URL` интеграционные тесты пропускаются. Линтеры: `make lint` (ruff и mypy --strict). В GitLab CI те же проверки идут в порядке lint → test → build.

## Конфигурация

Настройки читаются из переменных окружения или `.env` (`app/core/config.py`).

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://prices:prices@localhost:5432/prices` | PostgreSQL |
| `CELERY_BROKER_URL` | `amqp://guest:guest@localhost:5672//` | RabbitMQ |
| `REDIS_URL` | не задан | Кэш последней цены. Если не задан, API читает из БД |
| `DERIBIT_BASE_URL` | `https://www.deribit.com/api/v2` | Адрес API Deribit |
| `DERIBIT_TIMEOUT_SECONDS` | `10` | Таймаут запроса к бирже |
| `TICKERS` | `["btc_usd","eth_usd"]` | Какие тикеры собирать |
| `COLLECT_INTERVAL_SECONDS` | `60` | Период сбора |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

## Архитектура

![Компоненты](docs/diagrams/architecture.png)

![Слои приложения](docs/diagrams/layers.png)

- `app/api`: роутеры, зависимости, перевод доменных ошибок в HTTP
- `app/worker`: Celery-приложение, расписание и задача сбора
- `app/services`: `PriceService` (чтение для API) и `PriceCollector` (сбор цены)
- `app/repositories`, `app/clients`, `app/cache`: работа с PostgreSQL, Deribit и Redis
- `app/core`, `app/schemas`, `app/models`: настройки, тикеры, ошибки, Pydantic-схемы, ORM-модель

## Design decisions

**Нет глобального состояния.** Engine, сессии, HTTP-клиент и Redis создаются явно. API собирается фабрикой `create_app(settings)`, ресурсы создаются в `lifespan`, а сервис на каждый запрос собирается через `Depends`. Воркер берёт настройки из своего Celery-приложения (`PriceTrackerCelery.settings`). На уровне модуля есть только `celery_app` в `app/worker/main.py`: CLI `celery -A` ищет приложение как атрибут модуля.

**Сервисы зависят от протоколов.** `PriceService` и `PriceCollector` работают с `PriceReader`, `PriceWriter`, `PriceProvider` и `LatestPriceCache`, а не с конкретными классами. Поэтому в unit-тестах вместо них подставляются простые in-memory реализации, без моков.

**Celery и asyncio.** Задачи Celery синхронные, а клиент асинхронный (aiohttp), поэтому задача вызывает `asyncio.run(...)`. Подключения asyncpg привязаны к event loop, в котором открыты, поэтому engine создаётся на каждый запуск с `NullPool`. При двух задачах в минуту накладные расходы на это незаметны.

**Надёжность сбора.** На каждый тикер своя задача: если запрос по ETH упал, это не мешает BTC. Ошибки клиента разделены на временные (`DeribitUnavailableError`: сеть, таймаут, 5xx) и постоянные (`DeribitAPIError`). Celery повторяет только временные, не больше 3 раз и с экспоненциальной задержкой. Если задача простояла в очереди дольше интервала, она отбрасывается (`expires`). Кэш обновляется только после commit.

![Сбор цены](docs/diagrams/collect_sequence.png)

**Время берётся с биржи.** Сохраняется `usOut` из ответа Deribit (время сервера биржи), переведённое в секунды, а не время воркера. Оно не зависит от часов контейнера и задержек в очереди.

**Цена в `Decimal`.** Цена из JSON сразу переводится в `Decimal` через `str()`, в БД хранится как `NUMERIC(20, 8)`, а в API отдаётся строкой, чтобы клиент не потерял точность на float.

**Схема БД.** Таблица `prices(id, ticker, price, timestamp)` с составным индексом `(ticker, timestamp)`, которым пользуются все три запроса API. `timestamp` хранится как `BIGINT`, потому что задание требует UNIX timestamp. `ticker` хранится как `VARCHAR`, а не PG `ENUM`, чтобы добавлять валюты без миграции типа. Допустимые значения проверяет API. Схемой управляет Alembic.

![Схема БД](docs/diagrams/db_schema.png)

**API.** Пагинацию я добавил сверх задания: за месяц набегает около 43 000 записей на тикер, и отдавать их одним ответом нельзя. «Фильтр по дате» сделан как интервал `[date_from, date_to]`: границы включительные и каждая необязательна. Если `date_from` больше `date_to`, API отвечает `422`. `ticker` объявлен как `Enum`, поэтому FastAPI сам проверяет значение. Доменные ошибки переводятся в HTTP-ответы в одном месте (`app/api/errors.py`).

**Redis как кэш последней цены.** `/latest` запрашивают чаще всего, а меняется цена раз в минуту. Воркер после commit записывает цену в Redis с TTL в два интервала, API читает из Redis и при промахе идёт в PostgreSQL. Если Redis недоступен, это считается промахом. Без `REDIS_URL` используется `NullLatestPriceCache`.

![GET /api/v1/prices/latest](docs/diagrams/latest_sequence.png)

**RabbitMQ как брокер.** RabbitMQ надёжно доставляет сообщения и поддерживает подтверждения, это нужно для `task_acks_late`. Remote control, mingle и gossip в Celery отключены: им нужны transient-очереди, а RabbitMQ 4 их запрещает.

**Контейнеры.** Образ приложения один, он запускается в ролях `api`, `worker`, `beat` и `migrations`, БД работает в отдельном контейнере. Так каждый процесс перезапускается и масштабируется отдельно. Брокер и Redis добавлены, потому что они нужны Celery и кэшу.

## Что можно улучшить

- Keyset-пагинация (`?before=<timestamp>`) вместо `offset` для глубоких страниц.
- Партиционирование `prices` по времени и политика хранения при росте объёма.
- Метрики воркера и алерт на отставание сбора.
- Readiness-проба с проверкой БД.
