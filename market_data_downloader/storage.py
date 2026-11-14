import csv
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Iterable

from market_data_downloader.models import Candle, IndexInstrument


CSV_HEADER = (
    "Timestamp",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "OpenInterest",
)


def data_file_path(data_root: Path, instrument: IndexInstrument) -> Path:
    return (
        data_root
        / instrument.category.value
        / instrument.slug
        / f"{instrument.slug}_data.csv"
    )


def get_last_date_from_csv(filename: Path) -> date | None:
    if not filename.exists():
        return None

    latest_date: date | None = None
    with filename.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        header = next(reader, None)
        if header is None:
            return None
        if tuple(header) != CSV_HEADER:
            raise ValueError(f"Unexpected CSV header in {filename}.")

        for row_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != len(CSV_HEADER) or not row[0]:
                raise ValueError(f"Invalid candle row {row_number} in {filename}.")
            try:
                candle_date = date.fromisoformat(row[0].split("T", 1)[0])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid timestamp on row {row_number} in {filename}."
                ) from exc
            latest_date = max(latest_date, candle_date) if latest_date else candle_date

    return latest_date


def save_candles(filename: Path, candles: Iterable[Candle]) -> int:
    new_rows = list(candles)
    if not new_rows:
        return 0

    rows_by_timestamp: dict[str, list[object]] = {}
    if filename.exists():
        with filename.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.reader(file)
            header = next(reader, None)
            if tuple(header or ()) != CSV_HEADER:
                raise ValueError(f"Unexpected CSV header in {filename}.")
            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(CSV_HEADER) or not row[0]:
                    raise ValueError(f"Invalid candle row {row_number} in {filename}.")
                rows_by_timestamp[row[0]] = row

    for candle in new_rows:
        if len(candle) != len(CSV_HEADER) or not isinstance(candle[0], str):
            raise ValueError("Each candle must contain a timestamp and six values.")
        rows_by_timestamp[candle[0]] = list(candle)

    filename.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8",
            dir=filename.parent,
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            writer = csv.writer(file)
            writer.writerow(CSV_HEADER)
            for timestamp in sorted(rows_by_timestamp):
                writer.writerow(rows_by_timestamp[timestamp])
        os.replace(temporary_path, filename)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return len(new_rows)
