from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from market_data_downloader.data_repository import (
    CsvMarketDataRepository,
    MarketDataRepository,
)
from market_data_downloader.models import Candle, DataInstrument


class HistoricalDataSource(Protocol):
    def get_historical_candles(
        self,
        instrument_key: str,
        start_date: date,
        end_date: date,
        interval_minutes: int = 5,
    ) -> list[Candle]: ...


def next_start_date(
    data_root: Path,
    instrument: DataInstrument,
    first_download_date: date | None,
    repository: MarketDataRepository | None = None,
) -> date:
    data_repository = (
        repository
        if repository is not None
        else CsvMarketDataRepository(data_root)
    )
    last_date = data_repository.latest_date(instrument)
    if last_date is not None:
        return last_date + timedelta(days=1)
    if first_download_date is None:
        raise ValueError(f"Initial start date is required for {instrument.name}.")
    return first_download_date


def download_instrument(
    client: HistoricalDataSource,
    data_root: Path,
    instrument: DataInstrument,
    start_date: date,
    end_date: date,
    *,
    interval_minutes: int = 5,
    repository: MarketDataRepository | None = None,
) -> int:
    if start_date > end_date:
        return 0

    data_repository = (
        repository
        if repository is not None
        else CsvMarketDataRepository(data_root)
    )
    candles = client.get_historical_candles(
        instrument_key=instrument.instrument_key,
        start_date=start_date,
        end_date=end_date,
        interval_minutes=interval_minutes,
    )
    return data_repository.save(instrument, candles)
