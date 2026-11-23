import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.data_repository import CsvMarketDataRepository
from market_data_downloader.storage import data_file_path, save_candles


class CsvMarketDataRepositoryTests(unittest.TestCase):
    def test_reads_typed_candles_with_date_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instrument = BROAD_INDICES[0]
            save_candles(
                data_file_path(root, instrument),
                [
                    ["2026-10-26T15:25:00+05:30", 1, 2.5, 0, 1, 100, 4],
                    ["2026-10-27T09:15:00+05:30", 2, 3, 1, 2, 200, 5],
                ],
            )
            repository = CsvMarketDataRepository(root)

            candles = repository.load_candles(
                instrument,
                start_date=date(2026, 10, 27),
                end_date=date(2026, 10, 27),
            )

        self.assertEqual(len(candles), 1)
        self.assertEqual(
            candles[0],
            ["2026-10-27T09:15:00+05:30", 2, 3, 1, 2, 200, 5],
        )

    def test_reports_malformed_candle_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instrument = BROAD_INDICES[0]
            filename = data_file_path(root, instrument)
            filename.parent.mkdir(parents=True)
            filename.write_text(
                "Timestamp,Open,High,Low,Close,Volume,OpenInterest\n"
                "not-a-date,1,1,1,1,0,0\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Invalid timestamp"):
                CsvMarketDataRepository(root).load_candles(instrument)

    def test_rejects_non_numeric_candle_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instrument = BROAD_INDICES[0]
            filename = data_file_path(root, instrument)
            filename.parent.mkdir(parents=True)
            filename.write_text(
                "Timestamp,Open,High,Low,Close,Volume,OpenInterest\n"
                "2026-10-27T09:15:00+05:30,NaN,1,1,1,0,0\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Non-finite"):
                CsvMarketDataRepository(root).load_candles(instrument)


if __name__ == "__main__":
    unittest.main()
