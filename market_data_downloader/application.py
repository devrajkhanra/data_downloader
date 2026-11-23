from pathlib import Path
from typing import Callable

from market_data_downloader.data_repository import (
    CsvMarketDataRepository,
    MarketDataRepository,
)
from market_data_downloader.download_engine import (
    DEFAULT_MAX_WORKERS,
    DownloadEngine,
)
from market_data_downloader.downloader import HistoricalDataSource
from market_data_downloader.job_store import (
    DownloadJobStore,
    SQLiteJobStore,
)
from market_data_downloader.paths import DATA_ROOT, JOB_DB_PATH
from market_data_downloader.upstox_client import UpstoxClient


ClientFactory = Callable[[str], HistoricalDataSource]


class DownloadApplication:
    """Application composition root for the download use cases."""

    def __init__(
        self,
        data_root: Path = DATA_ROOT,
        job_database_path: Path = JOB_DB_PATH,
    ) -> None:
        self.data_root = data_root
        self.job_database_path = job_database_path

    def create_job_store(self) -> SQLiteJobStore:
        return SQLiteJobStore(self.job_database_path)

    def create_market_data_repository(self) -> MarketDataRepository:
        return CsvMarketDataRepository(self.data_root)

    def create_download_engine(
        self,
        access_token: str,
        *,
        max_workers: int = DEFAULT_MAX_WORKERS,
        job_store: DownloadJobStore | None = None,
        repository: MarketDataRepository | None = None,
        client_factory: ClientFactory = UpstoxClient,
    ) -> DownloadEngine:
        if not access_token.strip():
            raise ValueError("Access token is required.")
        return DownloadEngine(
            self.data_root,
            job_store if job_store is not None else self.create_job_store(),
            lambda: client_factory(access_token),
            repository=(
                repository
                if repository is not None
                else self.create_market_data_repository()
            ),
            max_workers=max_workers,
        )
