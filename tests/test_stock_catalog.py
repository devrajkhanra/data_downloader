import csv
import gzip
import io
import tempfile
import unittest
from pathlib import Path

import requests

from market_data_downloader.models import InstrumentCategory
from market_data_downloader.stock_catalog import (
    NSE_EQUITY_LIST_URL,
    InstrumentMasterError,
    load_nse_stocks,
)
from market_data_downloader.storage import data_file_path


UPSTOX_HEADER = (
    "instrument_key",
    "exchange_token",
    "tradingsymbol",
    "name",
    "last_price",
    "expiry",
    "strike",
    "tick_size",
    "lot_size",
    "instrument_type",
    "option_type",
    "exchange",
)
NSE_HEADER = (
    "SYMBOL",
    "NAME OF COMPANY",
    " SERIES",
    " DATE OF LISTING",
    " PAID UP VALUE",
    " MARKET LOT",
    " ISIN NUMBER",
    " FACE VALUE",
)


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, upstox_content, equity_content, fail_equity=False):
        self.upstox_content = upstox_content
        self.equity_content = equity_content
        self.fail_equity = fail_equity
        self.urls = []
        self.timeout = None
        self.timeouts = []
        self.request_kwargs = []

    def get(self, url, timeout, **kwargs):
        self.urls.append(url)
        self.timeout = timeout
        self.timeouts.append(timeout)
        self.request_kwargs.append(kwargs)
        if url == NSE_EQUITY_LIST_URL and self.fail_equity:
            raise requests.ConnectionError("NSE unavailable")
        content = (
            self.equity_content
            if url == NSE_EQUITY_LIST_URL
            else self.upstox_content
        )
        return FakeResponse(content)


def _csv_content(header, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def compressed_master(rows):
    return gzip.compress(_csv_content(UPSTOX_HEADER, rows))


def equity_list(rows):
    return _csv_content(NSE_HEADER, rows)


class StockCatalogTests(unittest.TestCase):
    def test_selects_eq_series_by_isin_and_reports_unmatched_symbols(self):
        upstox_content = compressed_master(
            [
                ["NSE_EQ|INE001", "1", "OLD-A", "Old A", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
                ["NSE_EQ|INE002", "2", "A-B", "Company B", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
                ["NSE_EQ|INE003", "3", "NOT_ACTIVE", "Inactive", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
                ["NSE_FO|INE004", "4", "OPTION", "Option", "10", "", "", "", "", "EQUITY", "", "NSE_FO"],
            ]
        )
        nse_content = equity_list(
            [
                ["NEW-A", "New Company A", "EQ", "", "10", "1", "INE001", "10"],
                ["A-B", "Company B", "EQ", "", "10", "1", "INE002", "10"],
                ["NOT_ACTIVE", "Inactive", "BE", "", "10", "1", "INE003", "10"],
                ["NO_UPSTOX_KEY", "New Listing", "EQ", "", "10", "1", "INE005", "10"],
            ]
        )
        session = FakeSession(upstox_content, nse_content)

        with tempfile.TemporaryDirectory() as directory:
            local_list = Path(directory) / "EQUITY_L.csv"
            catalog = load_nse_stocks(session, local_list)

            self.assertEqual(catalog.nse_eq_count, 3)
            self.assertEqual(len(catalog.instruments), 2)
            self.assertEqual(catalog.unmatched_symbols, ("NO_UPSTOX_KEY",))
            self.assertTrue(catalog.equity_list_refreshed)
            self.assertEqual(local_list.read_bytes(), nse_content)

        self.assertEqual(session.urls[0], NSE_EQUITY_LIST_URL)
        self.assertEqual(session.timeouts[0], (5, 15))
        self.assertEqual(
            session.request_kwargs[0]["headers"]["User-Agent"],
            "Mozilla/5.0",
        )
        self.assertEqual(session.timeout, 30)
        new_symbol_stock = next(
            stock
            for stock in catalog.instruments
            if stock.instrument_key == "NSE_EQ|INE001"
        )
        self.assertEqual(new_symbol_stock.tradingsymbol, "NEW-A")
        self.assertEqual(new_symbol_stock.name, "NEW-A - New Company A")
        self.assertEqual(new_symbol_stock.legacy_slugs, ("old-a",))
        self.assertTrue(
            all(
                stock.category is InstrumentCategory.STOCKS
                for stock in catalog.instruments
            )
        )

    def test_slug_generation_avoids_collisions_with_other_symbols(self):
        upstox_content = compressed_master(
            [
                ["NSE_EQ|INE001", "1", "A&B", "Company A", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
                ["NSE_EQ|INE002", "2", "A-B", "Company B", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
                ["NSE_EQ|INE003", "3", "A-B-INE001", "Company C", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
            ]
        )
        nse_content = equity_list(
            [
                ["A&B", "Company A", "EQ", "", "10", "1", "INE001", "10"],
                ["A-B", "Company B", "EQ", "", "10", "1", "INE002", "10"],
                ["A-B-INE001", "Company C", "EQ", "", "10", "1", "INE003", "10"],
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            catalog = load_nse_stocks(
                FakeSession(upstox_content, nse_content),
                Path(directory) / "EQUITY_L.csv",
            )

        stocks = catalog.instruments
        self.assertEqual(len({stock.slug for stock in stocks}), 3)
        stock = next(
            item for item in stocks if item.instrument_key == "NSE_EQ|INE003"
        )
        self.assertEqual(
            data_file_path(Path("data"), stock).as_posix(),
            "data/stocks/unclassified/a-b-ine001-2/a-b-ine001-2_data.csv",
        )

    def test_uses_local_nse_list_after_refresh_failure(self):
        upstox_content = compressed_master(
            [
                ["NSE_EQ|INE001", "1", "EXAMPLE", "Example Corp", "10", "", "", "", "", "EQUITY", "", "NSE_EQ"],
            ]
        )
        nse_content = equity_list(
            [["EXAMPLE", "Example Corp", "EQ", "", "10", "1", "INE001", "10"]]
        )

        with tempfile.TemporaryDirectory() as directory:
            local_list = Path(directory) / "EQUITY_L.csv"
            local_list.write_bytes(nse_content)
            catalog = load_nse_stocks(
                FakeSession(upstox_content, b"", fail_equity=True),
                local_list,
            )

        self.assertFalse(catalog.equity_list_refreshed)
        self.assertIn("NSE unavailable", catalog.equity_list_warning)
        self.assertEqual(len(catalog.instruments), 1)

    def test_unexpected_upstox_master_schema_is_reported(self):
        nse_content = equity_list(
            [["EXAMPLE", "Example Corp", "EQ", "", "10", "1", "INE001", "10"]]
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(InstrumentMasterError):
                load_nse_stocks(
                    FakeSession(
                        gzip.compress(b"not,a,valid,master\n1,2,3,4\n"),
                        nse_content,
                    ),
                    Path(directory) / "EQUITY_L.csv",
                )

    def test_unexpected_nse_list_schema_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(InstrumentMasterError):
                load_nse_stocks(
                    FakeSession(compressed_master([]), b"wrong,header\n"),
                    Path(directory) / "EQUITY_L.csv",
                )


if __name__ == "__main__":
    unittest.main()
