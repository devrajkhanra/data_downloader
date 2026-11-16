import csv
import gzip
import io
import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import requests

from market_data_downloader.models import InstrumentCategory, MarketInstrument
from market_data_downloader.paths import PROJECT_ROOT
from market_data_downloader.sessions import create_retrying_session


INSTRUMENT_MASTER_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
)
NSE_EQUITY_LIST_URL = (
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
)
EQUITY_LIST_PATH = PROJECT_ROOT / "EQUITY_L.csv"
REQUEST_TIMEOUT_SECONDS = 30
NSE_LIST_REQUEST_TIMEOUT = (5, 15)
NSE_EQUITY_LIST_HEADERS = {
    "Accept": "text/csv,*/*",
    "User-Agent": "Mozilla/5.0",
}
UPSTOX_REQUIRED_COLUMNS = {
    "EXCHANGE",
    "INSTRUMENT_KEY",
    "INSTRUMENT_TYPE",
    "NAME",
    "TRADINGSYMBOL",
}
NSE_REQUIRED_COLUMNS = {
    "ISIN NUMBER",
    "NAME OF COMPANY",
    "SERIES",
    "SYMBOL",
}


@dataclass(frozen=True)
class StockCatalog:
    instruments: tuple[MarketInstrument, ...]
    nse_eq_count: int
    unmatched_symbols: tuple[str, ...]
    equity_list_refreshed: bool
    equity_list_warning: str | None


class InstrumentMasterError(RuntimeError):
    """Raised when the current NSE and Upstox stock catalog cannot be loaded."""


def _base_slug(symbol: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", symbol.casefold()).strip("-")
    slug = slug or "unknown"
    if slug in {"aux", "con", "nul", "prn"} or re.fullmatch(
        r"(com|lpt)[1-9]",
        slug,
    ):
        return f"stock-{slug}"
    return slug


def _read_dict_reader(
    stream: TextIO,
    required_columns: set[str],
    source_name: str,
) -> csv.DictReader:
    reader = csv.DictReader(stream, skipinitialspace=True)
    if reader.fieldnames is None or any(
        not isinstance(field, str) for field in reader.fieldnames
    ):
        raise InstrumentMasterError(f"{source_name} has an unexpected format.")

    fieldnames = [field.strip().upper() for field in reader.fieldnames]
    if len(set(fieldnames)) != len(fieldnames):
        raise InstrumentMasterError(f"{source_name} has duplicate column names.")
    reader.fieldnames = fieldnames
    if not required_columns.issubset(fieldnames):
        raise InstrumentMasterError(f"{source_name} has an unexpected format.")
    return reader


def _read_nse_equities(stream: TextIO) -> dict[str, tuple[str, str]]:
    reader = _read_dict_reader(
        stream,
        NSE_REQUIRED_COLUMNS,
        "NSE equity list",
    )
    equities: dict[str, tuple[str, str]] = {}
    for row in reader:
        if (row.get("SERIES") or "").strip().upper() != "EQ":
            continue

        symbol = (row.get("SYMBOL") or "").strip()
        isin = (row.get("ISIN NUMBER") or "").strip().upper()
        name = re.sub(r"\s+", " ", (row.get("NAME OF COMPANY") or "").strip())
        if not symbol or not isin:
            raise InstrumentMasterError(
                "NSE equity list contains an EQ row without a symbol or ISIN."
            )
        if isin in equities:
            raise InstrumentMasterError(
                f"Duplicate ISIN in NSE equity list: {isin}."
            )
        equities[isin] = (symbol, name or symbol)

    if not equities:
        raise InstrumentMasterError("NSE equity list contains no SERIES=EQ entries.")
    return equities


def _read_nse_equities_from_bytes(content: bytes) -> dict[str, tuple[str, str]]:
    try:
        with io.TextIOWrapper(
            io.BytesIO(content),
            encoding="utf-8-sig",
            newline="",
        ) as text:
            return _read_nse_equities(text)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise InstrumentMasterError(f"Could not parse NSE equity list: {exc}") from exc


def _write_equity_list(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == content:
        return
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _make_unique_slugs(records: list[tuple[str, str]]) -> dict[str, str]:
    slug_counts = Counter(_base_slug(symbol) for symbol, _ in records)
    slugs: dict[str, str] = {}
    used_slugs: set[str] = set()
    for symbol, instrument_key in sorted(
        records,
        key=lambda record: (record[0].casefold(), record[1]),
    ):
        slug = _base_slug(symbol)
        if slug_counts[slug] > 1:
            key_suffix = re.sub(
                r"[^a-z0-9]+",
                "-",
                instrument_key.partition("|")[2].casefold(),
            )
            slug = f"{slug}-{key_suffix}"
        base_slug = slug
        suffix_number = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix_number}"
            suffix_number += 1
        used_slugs.add(slug)
        slugs[instrument_key] = slug
    return slugs


def _read_stocks(
    stream: TextIO,
    equities: dict[str, tuple[str, str]],
    *,
    equity_list_refreshed: bool,
    equity_list_warning: str | None,
) -> StockCatalog:
    reader = _read_dict_reader(
        stream,
        UPSTOX_REQUIRED_COLUMNS,
        "Upstox instrument master",
    )

    master_records: list[tuple[str, str, str]] = []
    seen_keys: set[str] = set()
    for row in reader:
        if (
            (row.get("EXCHANGE") or "").strip().upper() != "NSE_EQ"
            or (row.get("INSTRUMENT_TYPE") or "").strip().upper() != "EQUITY"
        ):
            continue

        instrument_key = (row.get("INSTRUMENT_KEY") or "").strip()
        symbol = (row.get("TRADINGSYMBOL") or "").strip()
        name = re.sub(r"\s+", " ", (row.get("NAME") or "").strip())
        isin = instrument_key.partition("|")[2].strip().upper()
        if not instrument_key.startswith("NSE_EQ|") or not symbol or not isin:
            raise InstrumentMasterError(
                "Upstox instrument master contains an invalid NSE equity row."
            )
        if instrument_key in seen_keys:
            raise InstrumentMasterError(
                f"Duplicate instrument key in Upstox master: {instrument_key}."
            )
        seen_keys.add(instrument_key)
        master_records.append((symbol, instrument_key, isin))

    if not master_records:
        raise InstrumentMasterError("No NSE_EQ/EQUITY instruments were found.")

    legacy_slugs = _make_unique_slugs(
        [(symbol, instrument_key) for symbol, instrument_key, _ in master_records]
    )
    matched_records: list[tuple[str, str, str]] = []
    seen_isins: set[str] = set()
    for _, instrument_key, isin in master_records:
        nse_equity = equities.get(isin)
        if nse_equity is None:
            continue
        if isin in seen_isins:
            raise InstrumentMasterError(
                f"Multiple Upstox keys match NSE ISIN {isin}."
            )
        seen_isins.add(isin)
        symbol, name = nse_equity
        matched_records.append((symbol, instrument_key, name))

    if not matched_records:
        raise InstrumentMasterError(
            "No current NSE SERIES=EQ securities matched Upstox instrument keys."
        )

    current_slugs = _make_unique_slugs(
        [(symbol, instrument_key) for symbol, instrument_key, _ in matched_records]
    )
    instruments: list[MarketInstrument] = []
    for symbol, instrument_key, name in sorted(
        matched_records,
        key=lambda record: (record[0].casefold(), record[1]),
    ):
        slug = current_slugs[instrument_key]
        old_slug = legacy_slugs[instrument_key]
        instruments.append(
            MarketInstrument(
                name=f"{symbol} - {name}" if name != symbol else symbol,
                instrument_key=instrument_key,
                category=InstrumentCategory.STOCKS,
                slug=slug,
                tradingsymbol=symbol,
                legacy_slugs=(old_slug,) if old_slug != slug else (),
            )
        )

    unmatched_symbols = tuple(
        sorted(
            symbol
            for isin, (symbol, _) in equities.items()
            if isin not in seen_isins
        )
    )
    return StockCatalog(
        instruments=tuple(instruments),
        nse_eq_count=len(equities),
        unmatched_symbols=unmatched_symbols,
        equity_list_refreshed=equity_list_refreshed,
        equity_list_warning=equity_list_warning,
    )


def _download_nse_equity_list(
    session: requests.Session,
    equity_list_path: Path,
) -> tuple[dict[str, tuple[str, str]], bool, str | None]:
    try:
        response = session.get(
            NSE_EQUITY_LIST_URL,
            headers=NSE_EQUITY_LIST_HEADERS,
            timeout=NSE_LIST_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        equities = _read_nse_equities_from_bytes(response.content)
        _write_equity_list(equity_list_path, response.content)
        return equities, True, None
    except (requests.RequestException, InstrumentMasterError, OSError) as exc:
        if not equity_list_path.exists():
            raise InstrumentMasterError(
                f"Could not refresh NSE equity list and no local copy is "
                f"available: {exc}"
            ) from exc
        try:
            local_equities = _read_nse_equities_from_bytes(
                equity_list_path.read_bytes()
            )
        except (OSError, InstrumentMasterError) as local_exc:
            raise InstrumentMasterError(
                f"Could not refresh NSE equity list ({exc}); local copy "
                f"{equity_list_path} is unusable: {local_exc}"
            ) from local_exc
        return local_equities, False, str(exc)


def _load_stocks(
    session: requests.Session,
    equity_list_path: Path,
) -> StockCatalog:
    equities, equity_list_refreshed, equity_list_warning = (
        _download_nse_equity_list(session, equity_list_path)
    )
    try:
        response = session.get(
            INSTRUMENT_MASTER_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise InstrumentMasterError(
            f"Could not download Upstox NSE instrument master: {exc}"
        ) from exc

    try:
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as compressed:
            with io.TextIOWrapper(
                compressed,
                encoding="utf-8-sig",
                newline="",
            ) as text:
                return _read_stocks(
                    text,
                    equities,
                    equity_list_refreshed=equity_list_refreshed,
                    equity_list_warning=equity_list_warning,
                )
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise InstrumentMasterError(
            f"Could not parse Upstox NSE instrument master: {exc}"
        ) from exc


def load_nse_stocks(
    session: requests.Session | None = None,
    equity_list_path: Path = EQUITY_LIST_PATH,
) -> StockCatalog:
    """Load current NSE SERIES=EQ stocks matched by ISIN to Upstox keys."""
    if session is not None:
        return _load_stocks(session, equity_list_path)

    with create_retrying_session() as session:
        return _load_stocks(session, equity_list_path)
