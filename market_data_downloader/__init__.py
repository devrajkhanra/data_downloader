"""Download historical NSE index data from Upstox."""

from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.models import IndexCategory, IndexInstrument

__all__ = [
    "ALL_INDICES",
    "BROAD_INDICES",
    "SECTORAL_INDICES",
    "IndexCategory",
    "IndexInstrument",
]
