from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from market_data_downloader.models import DataInstrument


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    CANCELLED = "cancelled"


class JobItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NO_DATA = "no_data"
    FAILED = "failed"


@dataclass(frozen=True)
class DownloadJobItem:
    job_id: str
    ordinal: int
    instrument: DataInstrument
    status: JobItemStatus
    saved_candles: int
    error: str | None


@dataclass(frozen=True)
class DownloadJob:
    job_id: str
    status: JobStatus
    first_download_date: date | None
    end_date: date
    interval_minutes: int
    total_items: int
    pending_items: int
    running_items: int
    succeeded_items: int
    no_data_items: int
    failed_items: int
    created_at: datetime
    updated_at: datetime
    error: str | None

    @property
    def completed_items(self) -> int:
        return (
            self.succeeded_items
            + self.no_data_items
            + self.failed_items
        )


@dataclass(frozen=True)
class DownloadProgress:
    job_id: str
    completed_items: int
    total_items: int
    succeeded_items: int
    no_data_items: int
    failed_items: int
    active_items: int
    instrument_name: str
    item_status: JobItemStatus
    saved_candles: int
    error: str | None
