import csv
import gzip
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TextIO

import requests

from market_data_downloader.catalog import ALL_INDICES
from market_data_downloader.models import MarketInstrument, OptionContract
from market_data_downloader.sessions import create_retrying_session
from market_data_downloader.stock_catalog import (
    EQUITY_LIST_PATH,
    INSTRUMENT_MASTER_URL,
    InstrumentMasterError,
    load_nse_stocks,
)


REQUEST_TIMEOUT_SECONDS = 30
OPTION_REQUIRED_COLUMNS = {
    "EXCHANGE",
    "INSTRUMENT_KEY",
    "INSTRUMENT_TYPE",
    "NAME",
    "TRADINGSYMBOL",
    "EXPIRY",
    "STRIKE",
    "OPTION_TYPE",
}
INDEX_OPTION_SLUGS = {
    "NIFTY": "nifty50",
    "NIFTYNXT50": "nifty-next-50",
    "BANKNIFTY": "nifty-bank",
    "FINNIFTY": "nifty-financial-services",
    "MIDCPNIFTY": "nifty-mid-select",
}


@dataclass(frozen=True)
class OptionCatalog:
    contracts: tuple[OptionContract, ...]
    stock_underlyings: int
    index_underlyings: int
    skipped_underlyings: tuple[str, ...]
    equity_list_refreshed: bool
    equity_list_warning: str | None


class OptionCatalogError(RuntimeError):
    """Raised when the listed option contracts cannot be loaded safely."""


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _read_master(stream: TextIO) -> list[dict[str, str]]:
    reader = csv.DictReader(stream, skipinitialspace=True)
    if reader.fieldnames is None or any(
        not isinstance(field, str) for field in reader.fieldnames
    ):
        raise OptionCatalogError("Upstox instrument master has an unexpected format.")

    fieldnames = [field.strip().upper() for field in reader.fieldnames]
    if len(set(fieldnames)) != len(fieldnames):
        raise OptionCatalogError("Upstox instrument master has duplicate columns.")
    if not OPTION_REQUIRED_COLUMNS.issubset(fieldnames):
        raise OptionCatalogError("Upstox instrument master has an unexpected format.")
    reader.fieldnames = fieldnames
    return list(reader)


def _stock_instrument_names(
    rows: list[dict[str, str]],
    active_stocks: tuple[MarketInstrument, ...],
) -> dict[str, MarketInstrument]:
    active_by_isin = {
        stock.instrument_key.partition("|")[2].upper(): stock
        for stock in active_stocks
    }
    isins_by_name: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if (
            (row.get("EXCHANGE") or "").strip().upper() != "NSE_EQ"
            or (row.get("INSTRUMENT_TYPE") or "").strip().upper() != "EQUITY"
        ):
            continue
        instrument_key = (row.get("INSTRUMENT_KEY") or "").strip()
        name = _normalize_name((row.get("NAME") or "").strip())
        if instrument_key.startswith("NSE_EQ|") and name:
            isins_by_name[name].add(instrument_key.partition("|")[2].upper())

    stocks_by_name: dict[str, MarketInstrument] = {}
    for name, isins in isins_by_name.items():
        active_matches = [active_by_isin[isin] for isin in isins if isin in active_by_isin]
        if len(active_matches) == 1:
            stocks_by_name[name] = active_matches[0]
    return stocks_by_name


def _make_contracts(
    rows: list[dict[str, str]],
    active_stocks: tuple[MarketInstrument, ...],
) -> OptionCatalog:
    stocks_by_name = _stock_instrument_names(rows, active_stocks)
    index_slugs = {
        _normalize_name(index.slug): index.slug
        for index in ALL_INDICES
    }
    index_slugs.update(
        {
            _normalize_name(alias): slug
            for alias, slug in INDEX_OPTION_SLUGS.items()
        }
    )

    records: list[
        tuple[str, str, str, date, Decimal, str, str, str]
    ] = []
    skipped_names: set[str] = set()
    seen_keys: set[str] = set()
    stock_underlyings: set[str] = set()
    index_underlyings: set[str] = set()
    today = date.today()

    for row in rows:
        exchange = (row.get("EXCHANGE") or "").strip().upper()
        instrument_type = (row.get("INSTRUMENT_TYPE") or "").strip().upper()
        option_type = (row.get("OPTION_TYPE") or "").strip().upper()
        if (
            exchange != "NSE_FO"
            or instrument_type not in {"OPTIDX", "OPTSTK"}
            or option_type not in {"CE", "PE"}
        ):
            continue

        instrument_key = (row.get("INSTRUMENT_KEY") or "").strip()
        trading_symbol = (row.get("TRADINGSYMBOL") or "").strip()
        underlying_name = (row.get("NAME") or "").strip()
        normalized_name = _normalize_name(underlying_name)
        if (
            not instrument_key.startswith("NSE_FO|")
            or not trading_symbol
            or not underlying_name
        ):
            raise OptionCatalogError(
                "Upstox instrument master contains an invalid option contract."
            )
        if instrument_key in seen_keys:
            raise OptionCatalogError(
                f"Duplicate option instrument key: {instrument_key}."
            )
        seen_keys.add(instrument_key)

        if instrument_type == "OPTIDX":
            underlying_slug = index_slugs.get(normalized_name)
            underlying_category = "indices"
            if underlying_slug is None:
                skipped_names.add(underlying_name)
                continue
        else:
            stock = stocks_by_name.get(normalized_name)
            if stock is None:
                skipped_names.add(underlying_name)
                continue
            underlying_slug = stock.slug
            underlying_category = "stocks"

        try:
            expiry_date = date.fromisoformat((row.get("EXPIRY") or "").strip())
            strike = Decimal((row.get("STRIKE") or "").strip())
        except (ValueError, InvalidOperation) as exc:
            raise OptionCatalogError(
                f"Invalid expiry or strike for {instrument_key}."
            ) from exc
        if expiry_date.isoformat() != (row.get("EXPIRY") or "").strip():
            raise OptionCatalogError(f"Invalid expiry for {instrument_key}.")
        if not strike.is_finite() or strike <= 0 or expiry_date < today:
            continue
        if underlying_category == "stocks":
            stock_underlyings.add(underlying_slug)
        else:
            index_underlyings.add(underlying_slug)

        records.append(
            (
                underlying_category,
                underlying_slug,
                underlying_name,
                expiry_date,
                strike,
                option_type,
                instrument_key,
                trading_symbol,
            )
        )

    last_expiry_by_month: dict[tuple[str, str, int, int], date] = {}
    for category, slug, _, expiry, _, _, _, _ in records:
        key = (category, slug, expiry.year, expiry.month)
        last_expiry_by_month[key] = max(last_expiry_by_month.get(key, expiry), expiry)

    contracts: list[OptionContract] = []
    for category, slug, underlying_name, expiry, strike, option_type, key, symbol in records:
        month_key = (category, slug, expiry.year, expiry.month)
        expiry_type = (
            "monthly" if expiry == last_expiry_by_month[month_key] else "weekly"
        )
        strike_text = format(strike.normalize(), "f")
        description = (
            f"{underlying_name} {expiry.isoformat()} {strike_text} {option_type}"
        )
        contracts.append(
            OptionContract(
                name=description if not symbol else f"{description} ({symbol})",
                instrument_key=key,
                underlying_category=category,
                underlying_slug=slug,
                expiry_type=expiry_type,
                expiry_date=expiry,
                strike_price=strike_text,
                option_type=option_type,
            )
        )

    contracts.sort(
        key=lambda contract: (
            contract.underlying_category,
            contract.underlying_slug,
            contract.expiry_date,
            Decimal(contract.strike_price),
            contract.option_type,
        )
    )
    return OptionCatalog(
        contracts=tuple(contracts),
        stock_underlyings=len(stock_underlyings),
        index_underlyings=len(index_underlyings),
        skipped_underlyings=tuple(sorted(skipped_names)),
        equity_list_refreshed=True,
        equity_list_warning=None,
    )


def _load_option_catalog(
    session: requests.Session,
    equity_list_path: Path,
) -> OptionCatalog:
    try:
        stock_catalog = load_nse_stocks(session, equity_list_path)
    except InstrumentMasterError as exc:
        raise OptionCatalogError(f"Could not load active NSE stocks: {exc}") from exc

    try:
        response = session.get(
            INSTRUMENT_MASTER_URL,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise OptionCatalogError(
            f"Could not download Upstox option contracts: {exc}"
        ) from exc

    try:
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as compressed:
            with io.TextIOWrapper(
                compressed,
                encoding="utf-8-sig",
                newline="",
            ) as text:
                catalog = _make_contracts(
                    _read_master(text),
                    stock_catalog.instruments,
                )
    except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
        raise OptionCatalogError(
            f"Could not parse Upstox option contracts: {exc}"
        ) from exc

    return OptionCatalog(
        contracts=catalog.contracts,
        stock_underlyings=catalog.stock_underlyings,
        index_underlyings=catalog.index_underlyings,
        skipped_underlyings=catalog.skipped_underlyings,
        equity_list_refreshed=stock_catalog.equity_list_refreshed,
        equity_list_warning=stock_catalog.equity_list_warning,
    )


def load_option_contracts(
    session: requests.Session | None = None,
    equity_list_path: Path = EQUITY_LIST_PATH,
) -> OptionCatalog:
    """Load currently listed NSE weekly and monthly option contracts."""
    if session is not None:
        return _load_option_catalog(session, equity_list_path)

    with create_retrying_session() as session:
        return _load_option_catalog(session, equity_list_path)
