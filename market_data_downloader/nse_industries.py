import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import requests

from market_data_downloader.models import MarketInstrument
from market_data_downloader.sessions import create_retrying_session


NSE_INDUSTRY_URL = (
    "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi"
)
NSE_REQUEST_TIMEOUT_SECONDS = 20
NSE_LOOKUP_DELAY_SECONDS = 0.25
INDUSTRY_CACHE_DAYS = 30
CACHE_BATCH_SIZE = 25
NSE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}

IndustryCache = dict[str, dict[str, str | None]]
ProgressCallback = Callable[[int, int, MarketInstrument], None]


class StockIndustryLookupError(RuntimeError):
    """Raised when NSE industry data cannot be retrieved or parsed."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _read_cache(cache_path: Path) -> IndustryCache:
    if not cache_path.exists():
        return {}

    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StockIndustryLookupError(
            f"Could not read NSE industry cache {cache_path}: {exc}"
        ) from exc
    if not isinstance(cache, dict):
        raise StockIndustryLookupError(
            f"NSE industry cache {cache_path} has an unexpected format."
        )

    validated: IndustryCache = {}
    for instrument_key, entry in cache.items():
        if (
            not isinstance(instrument_key, str)
            or not isinstance(entry, dict)
            or not isinstance(entry.get("checked_on"), str)
        ):
            raise StockIndustryLookupError(
                f"NSE industry cache {cache_path} has an invalid entry."
            )
        try:
            date.fromisoformat(entry["checked_on"])
        except ValueError as exc:
            raise StockIndustryLookupError(
                f"NSE industry cache has an invalid date for {instrument_key}."
            ) from exc
        sector = entry.get("sector")
        if sector is not None and not isinstance(sector, str):
            raise StockIndustryLookupError(
                f"NSE industry cache has an invalid sector for {instrument_key}."
            )
        validated[instrument_key] = {
            "checked_on": entry["checked_on"],
            "sector": sector,
        }
    return validated


def _write_cache(cache_path: Path, cache: IndustryCache) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_path.parent,
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(cache, file, ensure_ascii=False, sort_keys=True)
            file.write("\n")
        os.replace(temporary_path, cache_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _is_fresh(entry: dict[str, str | None] | None, today: date) -> bool:
    if entry is None:
        return False
    checked_on = date.fromisoformat(entry["checked_on"] or "")
    return (today - checked_on).days < INDUSTRY_CACHE_DAYS


def count_uncached_industries(
    stocks: tuple[MarketInstrument, ...],
    cache_path: Path,
    today: date | None = None,
) -> int:
    current_date = today or date.today()
    cache = _read_cache(cache_path)
    return sum(
        not _is_fresh(cache.get(stock.instrument_key), current_date)
        for stock in stocks
    )


def _extract_sector(payload: Any) -> str | None:
    if isinstance(payload, dict):
        security_info = payload.get("secInfo")
        if isinstance(security_info, dict):
            sector = security_info.get("sector")
            if isinstance(sector, str) and sector.strip():
                return sector.strip()
        industry_info = payload.get("industryInfo")
        if isinstance(industry_info, dict):
            sector = industry_info.get("sector")
            if isinstance(sector, str) and sector.strip():
                return sector.strip()
        for value in payload.values():
            sector = _extract_sector(value)
            if sector:
                return sector
    elif isinstance(payload, list):
        for value in payload:
            sector = _extract_sector(value)
            if sector:
                return sector
    return None


def _fetch_sector(
    session: requests.Session,
    stock: MarketInstrument,
) -> str | None:
    symbol = stock.tradingsymbol
    if not symbol:
        raise StockIndustryLookupError(
            f"Missing trading symbol for {stock.instrument_key}."
        )

    params = {
        "functionName": "getSymbolData",
        "marketType": "N",
        "series": "EQ",
        "symbol": symbol,
    }
    try:
        response = session.get(
            NSE_INDUSTRY_URL,
            params=params,
            headers=NSE_HEADERS,
            timeout=NSE_REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("equityResponse"), list)
        ):
            raise StockIndustryLookupError(
                f"NSE returned an unexpected industry response for {symbol}."
            )
        return _extract_sector(payload)
    except (requests.RequestException, ValueError) as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        raise StockIndustryLookupError(
            f"Could not load NSE industry for {symbol}: {exc}",
            status_code=status_code,
        ) from exc


def _sector_slug(sector: str | None) -> str | None:
    if not sector:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", sector.casefold()).strip("-")
    if not slug:
        return None
    if slug in {"aux", "con", "nul", "prn"} or re.fullmatch(
        r"(com|lpt)[1-9]",
        slug,
    ):
        return f"sector-{slug}"
    return slug


def _classify(
    stocks: tuple[MarketInstrument, ...],
    cache_path: Path,
    session: requests.Session,
    today: date,
    on_progress: ProgressCallback | None,
) -> tuple[MarketInstrument, ...]:
    cache = _read_cache(cache_path)
    pending = [
        stock
        for stock in stocks
        if not _is_fresh(cache.get(stock.instrument_key), today)
    ]
    if not pending:
        return tuple(
            replace(
                stock,
                sector_slug=_sector_slug(
                    (cache.get(stock.instrument_key) or {}).get("sector")
                ),
            )
            for stock in stocks
        )

    completed = 0
    try:
        for stock in pending:
            try:
                sector = _fetch_sector(session, stock)
            except StockIndustryLookupError:
                _write_cache(cache_path, cache)
                raise
            cache[stock.instrument_key] = {
                "checked_on": today.isoformat(),
                "sector": sector,
            }
            completed += 1
            if completed % CACHE_BATCH_SIZE == 0 or completed == len(pending):
                _write_cache(cache_path, cache)
            if on_progress is not None:
                on_progress(completed, len(pending), stock)
            if completed < len(pending):
                time.sleep(NSE_LOOKUP_DELAY_SECONDS)
    except OSError as exc:
        raise StockIndustryLookupError(
            f"Could not persist NSE industry cache {cache_path}: {exc}"
        ) from exc

    return tuple(
        replace(
            stock,
            sector_slug=_sector_slug(
                (cache.get(stock.instrument_key) or {}).get("sector")
            ),
        )
        for stock in stocks
    )


def classify_nse_industries(
    stocks: tuple[MarketInstrument, ...],
    cache_path: Path,
    session: requests.Session | None = None,
    today: date | None = None,
    on_progress: ProgressCallback | None = None,
) -> tuple[MarketInstrument, ...]:
    """Attach the NSE sector folder to each stock, caching lookup results."""
    current_date = today or date.today()
    if session is not None:
        return _classify(stocks, cache_path, session, current_date, on_progress)

    with create_retrying_session() as retrying_session:
        return _classify(
            stocks,
            cache_path,
            retrying_session,
            current_date,
            on_progress,
        )
