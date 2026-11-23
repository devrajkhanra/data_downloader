import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_data_downloader.models import InstrumentCategory, MarketInstrument
from market_data_downloader.stock_service import prepare_stock_instruments


class StockServiceTests(unittest.TestCase):
    def test_classifies_stocks_then_migrates_legacy_files(self):
        stock = MarketInstrument(
            name="Example Ltd",
            instrument_key="NSE_EQ|EXAMPLE",
            category=InstrumentCategory.STOCKS,
            slug="example",
            tradingsymbol="EXAMPLE",
        )
        classified = (
            MarketInstrument(
                name=stock.name,
                instrument_key=stock.instrument_key,
                category=stock.category,
                slug=stock.slug,
                tradingsymbol=stock.tradingsymbol,
                sector_slug="sample-sector",
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch(
                    "market_data_downloader.stock_service.classify_nse_industries",
                    return_value=classified,
                ) as classify,
                patch(
                    "market_data_downloader.stock_service.migrate_legacy_stock_file"
                ) as migrate,
            ):
                result = prepare_stock_instruments((stock,), root)

        self.assertEqual(result, classified)
        classify.assert_called_once_with(
            (stock,),
            root / ".stock_industry_cache.json",
            on_progress=None,
        )
        migrate.assert_called_once_with(root, classified[0])


if __name__ == "__main__":
    unittest.main()
