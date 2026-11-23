from pathlib import Path

from market_data_downloader.models import MarketInstrument
from market_data_downloader.nse_industries import (
    ProgressCallback,
    classify_nse_industries,
)
from market_data_downloader.storage import migrate_legacy_stock_file


def prepare_stock_instruments(
    stocks: tuple[MarketInstrument, ...],
    data_root: Path,
    *,
    cache_path: Path | None = None,
    on_progress: ProgressCallback | None = None,
) -> tuple[MarketInstrument, ...]:
    """Classify stocks and migrate their legacy CSVs before job creation."""
    industry_cache = (
        cache_path
        if cache_path is not None
        else data_root / ".stock_industry_cache.json"
    )
    classified = classify_nse_industries(
        stocks,
        industry_cache,
        on_progress=on_progress,
    )
    for instrument in classified:
        migrate_legacy_stock_file(data_root, instrument)
    return classified
