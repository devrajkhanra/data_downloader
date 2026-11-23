import csv
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Protocol

from market_data_downloader.models import Candle, DataInstrument
from market_data_downloader.storage import (
    CSV_HEADER,
    data_file_path,
    get_last_date_from_csv,
    save_candles,
)


class MarketDataRepository(Protocol):
    """Persistence port shared by ingestion and future analysis services."""

    def latest_date(self, instrument: DataInstrument) -> date | None: ...

    def load_candles(
        self,
        instrument: DataInstrument,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Candle]: ...

    def save(
        self,
        instrument: DataInstrument,
        candles: list[Candle],
    ) -> int: ...


class CsvMarketDataRepository:
    """CSV-backed market-data store with a stable read/write interface."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root

    def latest_date(self, instrument: DataInstrument) -> date | None:
        return get_last_date_from_csv(data_file_path(self._data_root, instrument))

    def load_candles(
        self,
        instrument: DataInstrument,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Candle]:
        filename = data_file_path(self._data_root, instrument)
        if not filename.exists():
            return []

        candles: list[Candle] = []
        with filename.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            header = next(reader, None)
            if tuple(header or ()) != CSV_HEADER:
                raise ValueError(f"Unexpected CSV header in {filename}.")

            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(CSV_HEADER) or not row[0]:
                    raise ValueError(
                        f"Invalid candle row {row_number} in {filename}."
                    )
                try:
                    candle_date = date.fromisoformat(row[0].split("T", 1)[0])
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid timestamp in row {row_number} of {filename}."
                    ) from exc
                if start_date is not None and candle_date < start_date:
                    continue
                if end_date is not None and candle_date > end_date:
                    continue

                candles.append(
                    [row[0], *(_parse_value(value) for value in row[1:])]
                )
        return candles

    def save(
        self,
        instrument: DataInstrument,
        candles: list[Candle],
    ) -> int:
        return save_candles(
            data_file_path(self._data_root, instrument),
            candles,
        )


def _parse_value(value: str) -> int | float | None:
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric candle value: {value}.") from exc
    if not isfinite(number):
        raise ValueError(f"Non-finite numeric candle value: {value}.")
    if number.is_integer():
        return int(number)
    return number
