import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.models import (
    IndexCategory,
    InstrumentCategory,
    MarketInstrument,
    OptionContract,
)
from market_data_downloader.storage import (
    CSV_HEADER,
    data_file_path,
    get_last_date_from_csv,
    migrate_legacy_stock_file,
    save_candles,
)


class StorageTests(unittest.TestCase):
    def test_nifty50_path_is_under_broad_indices(self):
        filename = data_file_path(Path("data"), BROAD_INDICES[0])
        self.assertEqual(
            filename,
            Path("data") / IndexCategory.BROAD.value / "nifty50" / "nifty50_data.csv",
        )

    def test_option_data_path_includes_underlying_expiry_and_strike(self):
        contract = OptionContract(
            name="NIFTY 2030-01-31 26000 CE",
            instrument_key="NSE_FO|12345",
            underlying_category="indices",
            underlying_slug="nifty50",
            expiry_type="monthly",
            expiry_date=date(2030, 1, 31),
            strike_price="26000",
            option_type="CE",
        )

        self.assertEqual(
            data_file_path(Path("data"), contract),
            Path("data")
            / "options"
            / "indices"
            / "nifty50"
            / "monthly"
            / "2030-01-31"
            / "26000-CE_data.csv",
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

    def test_latest_date_reads_last_row_and_ignores_trailing_blank_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "data.csv"
            with filename.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(CSV_HEADER)
                writer.writerow(["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0])
                writer.writerow(["2026-10-27T09:15:00+05:30", 2, 2, 2, 2, 0, 0])
                file.write("\n")

            self.assertEqual(get_last_date_from_csv(filename), date(2026, 10, 27))

    def test_stock_migration_merges_legacy_file_into_sector_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock = MarketInstrument(
                name="Example Corp",
                instrument_key="NSE_EQ|INE000A01001",
                category=InstrumentCategory.STOCKS,
                slug="example",
                tradingsymbol="EXAMPLE",
                sector_slug="information-technology",
            )
            legacy_path = root / "stocks" / "example" / "example_data.csv"
            target_path = data_file_path(root, stock)
            save_candles(
                legacy_path,
                [["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0]],
            )
            save_candles(
                target_path,
                [["2026-10-27T09:15:00+05:30", 2, 2, 2, 2, 0, 0]],
            )

            self.assertTrue(migrate_legacy_stock_file(root, stock))

            with target_path.open("r", newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))
            self.assertEqual(len(rows), 3)
            self.assertFalse(legacy_path.exists())
            self.assertEqual(get_last_date_from_csv(target_path), date(2026, 10, 27))

    def test_stock_migration_merges_legacy_file_into_sector_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock = MarketInstrument(
                name="Example Corp",
                instrument_key="NSE_EQ|INE000A01001",
                category=InstrumentCategory.STOCKS,
                slug="example",
                tradingsymbol="EXAMPLE",
                sector_slug="information-technology",
            )
            legacy_path = root / "stocks" / "example" / "example_data.csv"
            target_path = data_file_path(root, stock)
            save_candles(
                legacy_path,
                [["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0]],
            )
            save_candles(
                target_path,
                [["2026-10-27T09:15:00+05:30", 2, 2, 2, 2, 0, 0]],
            )

            self.assertTrue(migrate_legacy_stock_file(root, stock))

            with target_path.open("r", newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))
            self.assertEqual(len(rows), 3)
            self.assertFalse(legacy_path.exists())
            self.assertEqual(get_last_date_from_csv(target_path), date(2026, 10, 27))

    def test_stock_migration_finds_renamed_symbol_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock = MarketInstrument(
                name="New Company Name",
                instrument_key="NSE_EQ|INE000A01001",
                category=InstrumentCategory.STOCKS,
                slug="newco",
                tradingsymbol="NEWCO",
                sector_slug="industrial-products",
                legacy_slugs=("oldco",),
            )
            legacy_path = root / "stocks" / "oldco" / "oldco_data.csv"
            save_candles(
                legacy_path,
                [["2026-10-26T15:25:00+05:30", 1, 1, 1, 1, 0, 0]],
            )

            self.assertTrue(migrate_legacy_stock_file(root, stock))

            self.assertFalse(legacy_path.exists())
            self.assertTrue(data_file_path(root, stock).exists())
            self.assertEqual(
                get_last_date_from_csv(data_file_path(root, stock)),
                date(2026, 10, 26),
            )


if __name__ == "__main__":
    unittest.main()
