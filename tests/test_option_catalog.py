import csv
import gzip
import io
import tempfile
import unittest
from pathlib import Path

from market_data_downloader.option_catalog import (
    OptionCatalogError,
    load_option_contracts,
)
from market_data_downloader.stock_catalog import (
    INSTRUMENT_MASTER_URL,
    NSE_EQUITY_LIST_URL,
)


MASTER_HEADER = (
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
EQUITY_HEADER = (
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
    def __init__(self, equity_content, master_content):
        self.equity_content = equity_content
        self.master_content = master_content
        self.urls = []
        self.timeouts = []
        self.request_headers = []

    def get(self, url, timeout, **kwargs):
        self.urls.append(url)
        self.timeouts.append(timeout)
        self.request_headers.append(kwargs.get("headers"))
        if url == NSE_EQUITY_LIST_URL:
            return FakeResponse(self.equity_content)
        return FakeResponse(self.master_content)


def csv_content(header, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def compressed_master(rows):
    return gzip.compress(csv_content(MASTER_HEADER, rows))


def equity_list(rows):
    return csv_content(EQUITY_HEADER, rows)


def master_row(key, symbol, name, expiry, strike, instrument_type, option_type, exchange):
    return [
        key,
        key.partition("|")[2],
        symbol,
        name,
        "1",
        expiry,
        strike,
        "0.05",
        "1",
        instrument_type,
        option_type,
        exchange,
    ]


class OptionCatalogTests(unittest.TestCase):
    def test_selects_current_index_and_active_stock_options_by_expiry(self):
        rows = [
            master_row("NSE_EQ|INE001", "EXAMPLE", "EXAMPLE LTD", "", "", "EQUITY", "", "NSE_EQ"),
            master_row("NSE_EQ|INE002", "OLDCO", "OLD LTD", "", "", "EQUITY", "", "NSE_EQ"),
            master_row("NSE_FO|IDX1", "NIFTY20300103CE100", "NIFTY", "2030-01-03", "100", "OPTIDX", "CE", "NSE_FO"),
            master_row("NSE_FO|IDX2", "NIFTY20300131CE100", "NIFTY", "2030-01-31", "100", "OPTIDX", "CE", "NSE_FO"),
            master_row("NSE_FO|IDX3", "NIFTY20300131PE100", "NIFTY", "2030-01-31", "100", "OPTIDX", "PE", "NSE_FO"),
            master_row("NSE_FO|STK1", "EXAMPLE20300207CE10", "EXAMPLE LTD", "2030-02-07", "10.0", "OPTSTK", "CE", "NSE_FO"),
            master_row("NSE_FO|STK2", "EXAMPLE20300228PE10", "EXAMPLE LTD", "2030-02-28", "10.0", "OPTSTK", "PE", "NSE_FO"),
            master_row("NSE_FO|OLD1", "OLD20300228CE10", "OLD LTD", "2030-02-28", "10", "OPTSTK", "CE", "NSE_FO"),
            master_row("NSE_FO|UNSUPPORTED", "NIFTYFPI20300228CE10", "NIFTYFPI", "2030-02-28", "10", "OPTIDX", "CE", "NSE_FO"),
            master_row("NSE_FO|EXPIRED", "NIFTY20200130CE100", "NIFTY", "2020-01-30", "100", "OPTIDX", "CE", "NSE_FO"),
        ]
        session = FakeSession(
            equity_list(
                [
                    ["EXAMPLE", "Example Limited", "EQ", "", "10", "1", "INE001", "10"],
                    ["OLDCO", "Old Limited", "BE", "", "10", "1", "INE002", "10"],
                ]
            ),
            compressed_master(rows),
        )

        with tempfile.TemporaryDirectory() as directory:
            catalog = load_option_contracts(
                session,
                Path(directory) / "EQUITY_L.csv",
            )

        self.assertEqual(len(catalog.contracts), 5)
        self.assertEqual(catalog.index_underlyings, 1)
        self.assertEqual(catalog.stock_underlyings, 1)
        self.assertEqual(
            catalog.skipped_underlyings,
            ("NIFTYFPI", "OLD LTD"),
        )
        by_key = {contract.instrument_key: contract for contract in catalog.contracts}
        self.assertEqual(by_key["NSE_FO|IDX1"].expiry_type, "weekly")
        self.assertEqual(by_key["NSE_FO|IDX2"].expiry_type, "monthly")
        self.assertEqual(by_key["NSE_FO|STK1"].underlying_slug, "example")
        self.assertEqual(by_key["NSE_FO|STK2"].expiry_type, "monthly")
        self.assertEqual(session.urls.count(INSTRUMENT_MASTER_URL), 2)
        self.assertEqual(session.timeouts, [(5, 15), 30, 30])
        self.assertEqual(
            session.request_headers[0]["User-Agent"],
            "Mozilla/5.0",
        )

    def test_rejects_an_unexpected_instrument_master_schema(self):
        session = FakeSession(
            equity_list(
                [["EXAMPLE", "Example Limited", "EQ", "", "10", "1", "INE001", "10"]]
            ),
            gzip.compress(b"not,a,valid,master\n1,2,3,4\n"),
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OptionCatalogError):
                load_option_contracts(
                    session,
                    Path(directory) / "EQUITY_L.csv",
                )


if __name__ == "__main__":
    unittest.main()
