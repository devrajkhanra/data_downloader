import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.downloader import download_index, next_start_date
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
            saved = download_index(
                client,
                root,
                instrument,
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            self.assertEqual(saved, 1)
            self.assertTrue(data_file_path(root, instrument).exists())
            self.assertEqual(client.calls[0][0], instrument.instrument_key)


if __name__ == "__main__":
    unittest.main()
