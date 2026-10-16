from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.tickers import Ticker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://prices:prices@localhost:5432/prices"),
    )
    redis_url: str | None = Field(
        default=None,
        description="Latest-price cache. When empty, the API reads straight from PostgreSQL.",
    )
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"

    deribit_base_url: str = "https://www.deribit.com/api/v2"
    deribit_timeout_seconds: float = Field(default=10.0, gt=0)

    tickers: list[Ticker] = Field(default_factory=lambda: list(Ticker))
    collect_interval_seconds: int = Field(default=60, gt=0)

    log_level: str = "INFO"

    @property
    def database_dsn(self) -> str:
        return str(self.database_url)

    @property
    def latest_price_cache_ttl_seconds(self) -> int:
        return self.collect_interval_seconds * 2
