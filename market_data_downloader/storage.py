import csv
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Iterable

from market_data_downloader.models import (
    Candle,
    DataInstrument,
    InstrumentCategory,
    MarketInstrument,
    OptionContract,
)


CSV_HEADER = (
    "Timestamp",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "OpenInterest",
)


def data_file_path(data_root: Path, instrument: DataInstrument) -> Path:
    if isinstance(instrument, OptionContract):
        strike_slug = instrument.strike_price.replace(".", "-")
        filename = f"{strike_slug}-{instrument.option_type}_data.csv"
        return (
            data_root
            / "options"
            / instrument.underlying_category
            / instrument.underlying_slug
            / instrument.expiry_type
            / instrument.expiry_date.isoformat()
            / filename
        )
    if instrument.category is InstrumentCategory.STOCKS:
        sector_slug = instrument.sector_slug or "unclassified"
        return (
            data_root
            / instrument.category.value
            / sector_slug
            / instrument.slug
            / f"{instrument.slug}_data.csv"
        )
    return (
        data_root
        / instrument.category.value
        / instrument.slug
        / f"{instrument.slug}_data.csv"
    )


def get_last_date_from_csv(filename: Path) -> date | None:
    if not filename.exists():
        return None

    with filename.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        header = next(reader, None)
        if header is None:
            return None
        if tuple(header) != CSV_HEADER:
            raise ValueError(f"Unexpected CSV header in {filename}.")

    with filename.open("rb") as file:
        end = file.seek(0, os.SEEK_END)
        while end > 0:
            file.seek(end - 1)
            if file.read(1) not in (b"\n", b"\r"):
                break
            end -= 1
        if end == 0:
            return None

        start = end
        while start > 0:
            file.seek(start - 1)
            if file.read(1) == b"\n":
                break
            start -= 1
        file.seek(start)
        line = file.read(end - start)
        row = next(csv.reader([line.decode("utf-8-sig")]), None)

    if row is None or tuple(row) == CSV_HEADER:
        return None
    if len(row) != len(CSV_HEADER) or not row[0]:
        raise ValueError(f"Invalid final candle row in {filename}.")
    try:
        return date.fromisoformat(row[0].split("T", 1)[0])
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp in final row of {filename}.") from exc


def migrate_legacy_stock_file(
    data_root: Path,
    instrument: MarketInstrument,
) -> bool:
    if instrument.category is not InstrumentCategory.STOCKS:
        return False

    current_path = data_file_path(data_root, instrument)
    legacy_slugs = dict.fromkeys((instrument.slug, *instrument.legacy_slugs))
    migrated = False
    for legacy_slug in legacy_slugs:
        legacy_path = (
            data_root
            / instrument.category.value
            / legacy_slug
            / f"{legacy_slug}_data.csv"
        )
        if legacy_path == current_path or not legacy_path.exists():
            continue

        if current_path.exists():
            with legacy_path.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.reader(file)
                header = next(reader, None)
                if tuple(header or ()) != CSV_HEADER:
                    raise ValueError(f"Unexpected CSV header in {legacy_path}.")
                rows = list(reader)
            save_candles(current_path, rows)
            legacy_path.unlink()
        else:
            current_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(legacy_path, current_path)
        migrated = True
    return migrated


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
