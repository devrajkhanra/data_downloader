import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.models import IndexCategory
from market_data_downloader.storage import (
    CSV_HEADER,
    data_file_path,
    get_last_date_from_csv,
    save_candles,
)


class StorageTests(unittest.TestCase):
    def test_nifty50_path_is_under_broad_indices(self):
        filename = data_file_path(Path("data"), BROAD_INDICES[0])
        self.assertEqual(
            filename,
            Path("data") / IndexCategory.BROAD.value / "nifty50" / "nifty50_data.csv",
        )

    def test_save_merges_candles_without_duplicates_and_sorts_them(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "nifty50_data.csv"
            first = ["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0]
            updated = ["2026-10-27T09:15:00+05:30", 3, 3, 3, 3, 0, 0]
            original = ["2026-10-27T09:15:00+05:30", 2, 2, 2, 2, 0, 0]

            save_candles(filename, [updated, first])
            save_candles(filename, [original])

            with filename.open(newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))
            self.assertEqual(tuple(rows[0]), CSV_HEADER)
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[-1][0], original[0])
            self.assertEqual(rows[-1][1], "2")
            self.assertEqual(get_last_date_from_csv(filename), date(2026, 10, 27))

    def test_empty_response_does_not_create_or_truncate_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "data.csv"
            self.assertEqual(save_candles(filename, []), 0)
            self.assertFalse(filename.exists())

            filename.write_text("existing", encoding="utf-8")
            self.assertEqual(save_candles(filename, []), 0)
            self.assertEqual(filename.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
