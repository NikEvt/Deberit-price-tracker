from app.core.tickers import Ticker


class PriceTrackerError(Exception):
    pass


class PriceNotFoundError(PriceTrackerError):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"No prices stored for ticker {ticker.value!r}")
        self.ticker = ticker


class InvalidDateRangeError(PriceTrackerError):
    def __init__(self) -> None:
        super().__init__("date_from must be less than or equal to date_to")
