import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.downloader import download_instrument, next_start_date
from market_data_downloader.models import (
    InstrumentCategory,
    MarketInstrument,
    OptionContract,
)
from market_data_downloader.storage import data_file_path, save_candles


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_historical_candles(
        self,
        instrument_key,
        start_date,
        end_date,
        interval_minutes,
    ):
        self.calls.append((instrument_key, start_date, end_date, interval_minutes))
        return [["2026-10-27T09:15:00+05:30", 1, 1, 1, 1, 0, 0]]


class DownloaderTests(unittest.TestCase):
    def test_existing_index_resumes_after_latest_csv_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instrument = BROAD_INDICES[0]
            save_candles(
                data_file_path(root, instrument),
                [["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0]],
            )

            self.assertEqual(
                next_start_date(root, instrument, None),
                date(2026, 10, 27),
            )

    def test_first_download_uses_user_start_date(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                next_start_date(
                    Path(directory),
                    BROAD_INDICES[0],
                    date(2022, 1, 1),
                ),
                date(2022, 1, 1),
            )

    def test_download_writes_to_the_index_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = FakeClient()
            instrument = BROAD_INDICES[0]
            saved = download_instrument(
                client,
                root,
                instrument,
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            self.assertEqual(saved, 1)
            self.assertTrue(data_file_path(root, instrument).exists())
            self.assertEqual(client.calls[0][0], instrument.instrument_key)

    def test_download_writes_stock_to_its_symbol_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = FakeClient()
            stock = MarketInstrument(
                name="Example Corp",
                instrument_key="NSE_EQ|INE000A01001",
                category=InstrumentCategory.STOCKS,
                slug="example",
                tradingsymbol="EXAMPLE",
                sector_slug="information-technology",
            )

            saved = download_instrument(
                client,
                root,
                stock,
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            self.assertEqual(saved, 1)
            self.assertEqual(
                data_file_path(root, stock),
                root
                / "stocks"
                / "information-technology"
                / "example"
                / "example_data.csv",
            )
            self.assertTrue(data_file_path(root, stock).exists())

    def test_option_contract_uses_shared_download_and_resume_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = FakeClient()
            contract = OptionContract(
                name="NIFTY 2026-12-31 26000 CE",
                instrument_key="NSE_FO|12345",
                underlying_category="indices",
                underlying_slug="nifty50",
                expiry_type="monthly",
                expiry_date=date(2026, 12, 31),
                strike_price="26000",
                option_type="CE",
            )
            filename = data_file_path(root, contract)

            saved = download_instrument(
                client,
                root,
                contract,
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            self.assertEqual(saved, 1)
            self.assertEqual(client.calls[0][0], contract.instrument_key)
            self.assertEqual(
                next_start_date(root, contract, None),
                date(2026, 10, 28),
            )
            self.assertTrue(filename.exists())


if __name__ == "__main__":
    unittest.main()
