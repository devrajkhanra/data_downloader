from datetime import date, timedelta
from pathlib import Path

from market_data_downloader.models import IndexInstrument
from market_data_downloader.storage import data_file_path, get_last_date_from_csv, save_candles
from market_data_downloader.upstox_client import UpstoxClient


def next_start_date(
    data_root: Path,
    instrument: IndexInstrument,
    first_download_date: date | None,
) -> date:
    filename = data_file_path(data_root, instrument)
    last_date = get_last_date_from_csv(filename)
    if last_date is not None:
        return last_date + timedelta(days=1)
    if first_download_date is None:
        raise ValueError(f"Initial start date is required for {instrument.name}.")
    return first_download_date


def download_index(
    client: UpstoxClient,
    data_root: Path,
    instrument: IndexInstrument,
    start_date: date,
    end_date: date,
) -> int:
    if start_date > end_date:
        return 0

    candles = client.get_historical_candles(
        instrument_key=instrument.instrument_key,
        start_date=start_date,
        end_date=end_date,
        interval_minutes=5,
    )
    return save_candles(data_file_path(data_root, instrument), candles)
