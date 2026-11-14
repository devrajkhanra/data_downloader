import unittest
from datetime import date

from market_data_downloader.date_ranges import month_ranges, parse_iso_date


class DateRangeTests(unittest.TestCase):
    def test_month_ranges_preserve_start_day_and_split_at_month_boundaries(self):
        self.assertEqual(
            month_ranges(date(2026, 10, 27), date(2026, 11, 14)),
            [
                (date(2026, 10, 27), date(2026, 10, 31)),
                (date(2026, 11, 1), date(2026, 11, 14)),
            ],
        )

    def test_month_ranges_return_empty_for_reversed_dates(self):
        self.assertEqual(month_ranges(date(2026, 11, 1), date(2026, 10, 31)), [])

    def test_date_parser_requires_zero_padded_iso_format(self):
        self.assertEqual(parse_iso_date("2026-10-27"), date(2026, 10, 27))
        with self.assertRaises(ValueError):
            parse_iso_date("2026-1-2")


if __name__ == "__main__":
    unittest.main()
