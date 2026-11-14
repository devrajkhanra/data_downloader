import unittest

from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.models import IndexCategory


class CatalogTests(unittest.TestCase):
    def test_catalog_has_unique_keys_and_output_paths(self):
        self.assertEqual(len({item.instrument_key for item in ALL_INDICES}), len(ALL_INDICES))
        self.assertEqual(
            len({(item.category, item.slug) for item in ALL_INDICES}),
            len(ALL_INDICES),
        )
        self.assertTrue(all(item.instrument_key.startswith("NSE_INDEX|") for item in ALL_INDICES))

    def test_broad_and_sectoral_groups_are_separate(self):
        self.assertTrue(all(item.category is IndexCategory.BROAD for item in BROAD_INDICES))
        self.assertTrue(
            all(item.category is IndexCategory.SECTORAL for item in SECTORAL_INDICES)
        )
        nifty50 = next(item for item in BROAD_INDICES if item.name == "Nifty 50")
        self.assertEqual(nifty50.slug, "nifty50")


if __name__ == "__main__":
    unittest.main()
