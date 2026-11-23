import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator, Protocol

from market_data_downloader.job_models import (
    DownloadJob,
    DownloadJobItem,
    JobItemStatus,
    JobStatus,
)
from market_data_downloader.models import (
    DataInstrument,
    InstrumentCategory,
    MarketInstrument,
    OptionContract,
)


SCHEMA_VERSION = 1


class DownloadJobStore(Protocol):
    def create_job(
        self,
        instruments: tuple[DataInstrument, ...],
        first_download_date: date | None,
        end_date: date,
        interval_minutes: int,
    ) -> str: ...

    def get_job(self, job_id: str) -> DownloadJob: ...

    def list_jobs(self, limit: int = 50) -> tuple[DownloadJob, ...]: ...

    def get_items(
        self,
        job_id: str,
        statuses: tuple[JobItemStatus, ...] | None = None,
    ) -> tuple[DownloadJobItem, ...]: ...

    def start_job(self, job_id: str, recover_running: bool = False) -> DownloadJob: ...

    def mark_item_running(self, job_id: str, ordinal: int) -> None: ...

    def finish_item(
        self,
        job_id: str,
        ordinal: int,
        status: JobItemStatus,
        saved_candles: int,
        error: str | None = None,
    ) -> None: ...

    def finish_job(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> DownloadJob: ...


class SQLiteJobStore:
    """Durable job and per-instrument state for the download engine."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        with closing(
            sqlite3.connect(self._database_path, timeout=30)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Job database version {version} is newer than supported "
                    f"version {SCHEMA_VERSION}."
                )
            if version == 0:
                with connection:
                    connection.executescript(
                        """
                        CREATE TABLE jobs (
                            id TEXT PRIMARY KEY,
                            status TEXT NOT NULL,
                            first_download_date TEXT,
                            end_date TEXT NOT NULL,
                            interval_minutes INTEGER NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            error TEXT
                        );

                        CREATE TABLE job_items (
                            job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                            ordinal INTEGER NOT NULL,
                            instrument_key TEXT NOT NULL,
                            instrument_json TEXT NOT NULL,
                            status TEXT NOT NULL,
                            saved_candles INTEGER NOT NULL DEFAULT 0,
                            error TEXT,
                            PRIMARY KEY (job_id, ordinal),
                            UNIQUE (job_id, instrument_key)
                        );

                        CREATE INDEX job_items_status_idx
                            ON job_items(job_id, status, ordinal);
                        PRAGMA user_version = 1;
                        """
                    )

    def create_job(
        self,
        instruments: tuple[DataInstrument, ...],
        first_download_date: date | None,
        end_date: date,
        interval_minutes: int,
    ) -> str:
        if not instruments:
            raise ValueError("A download job must include at least one instrument.")
        if first_download_date is not None and first_download_date > end_date:
            raise ValueError("The initial start date cannot be after the end date.")
        if not 1 <= interval_minutes <= 15:
            raise ValueError("Minute intervals must be from 1 to 15.")
        keys = [instrument.instrument_key for instrument in instruments]
        if len(set(keys)) != len(keys):
            raise ValueError("A download job cannot contain duplicate instruments.")

        job_id = str(uuid.uuid4())
        now = _utc_now()
        with self._connection() as connection, connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, status, first_download_date, end_date,
                    interval_minutes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    JobStatus.QUEUED.value,
                    first_download_date.isoformat()
                    if first_download_date is not None
                    else None,
                    end_date.isoformat(),
                    interval_minutes,
                    now,
                    now,
                ),
            )
            connection.executemany(
                """
                INSERT INTO job_items (
                    job_id, ordinal, instrument_key, instrument_json, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (
                        job_id,
                        ordinal,
                        instrument.instrument_key,
                        json.dumps(_serialize_instrument(instrument)),
                        JobItemStatus.PENDING.value,
                    )
                    for ordinal, instrument in enumerate(instruments)
                ),
            )
        return job_id

    def get_job(self, job_id: str) -> DownloadJob:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    j.*,
                    COUNT(i.ordinal) AS total_items,
                    SUM(i.status = 'pending') AS pending_items,
                    SUM(i.status = 'running') AS running_items,
                    SUM(i.status = 'succeeded') AS succeeded_items,
                    SUM(i.status = 'no_data') AS no_data_items,
                    SUM(i.status = 'failed') AS failed_items
                FROM jobs AS j
                LEFT JOIN job_items AS i ON i.job_id = j.id
                WHERE j.id = ?
                GROUP BY j.id
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown download job: {job_id}")
        return DownloadJob(
            job_id=row["id"],
            status=JobStatus(row["status"]),
            first_download_date=(
                date.fromisoformat(row["first_download_date"])
                if row["first_download_date"]
                else None
            ),
            end_date=date.fromisoformat(row["end_date"]),
            interval_minutes=row["interval_minutes"],
            total_items=row["total_items"],
            pending_items=row["pending_items"] or 0,
            running_items=row["running_items"] or 0,
            succeeded_items=row["succeeded_items"] or 0,
            no_data_items=row["no_data_items"] or 0,
            failed_items=row["failed_items"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error=row["error"],
        )

    def list_jobs(self, limit: int = 50) -> tuple[DownloadJob, ...]:
        if limit < 1:
            raise ValueError("Job list limit must be positive.")
        with self._connection() as connection:
            ids = [
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            ]
        return tuple(self.get_job(job_id) for job_id in ids)

    def get_items(
        self,
        job_id: str,
        statuses: tuple[JobItemStatus, ...] | None = None,
    ) -> tuple[DownloadJobItem, ...]:
        with self._connection() as connection:
            if statuses is None:
                rows = connection.execute(
                    """
                    SELECT * FROM job_items
                    WHERE job_id = ? ORDER BY ordinal
                    """,
                    (job_id,),
                ).fetchall()
            elif not statuses:
                rows = []
            else:
                placeholders = ",".join("?" for _ in statuses)
                rows = connection.execute(
                    f"""
                    SELECT * FROM job_items
                    WHERE job_id = ? AND status IN ({placeholders})
                    ORDER BY ordinal
                    """,
                    (job_id, *(status.value for status in statuses)),
                ).fetchall()
        return tuple(
            DownloadJobItem(
                job_id=row["job_id"],
                ordinal=row["ordinal"],
                instrument=_deserialize_instrument(
                    json.loads(row["instrument_json"])
                ),
                status=JobItemStatus(row["status"]),
                saved_candles=row["saved_candles"],
                error=row["error"],
            )
            for row in rows
        )

    def start_job(self, job_id: str, recover_running: bool = False) -> DownloadJob:
        with self._connection() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown download job: {job_id}")
            status = JobStatus(row["status"])
            if status is JobStatus.RUNNING and not recover_running:
                raise RuntimeError(
                    f"Download job {job_id} is already marked as running."
                )
            if status is JobStatus.COMPLETED:
                raise RuntimeError(f"Download job {job_id} is already complete.")

            now = _utc_now()
            connection.execute(
                """
                UPDATE job_items
                SET status = ?, error = NULL
                WHERE job_id = ? AND status IN (?, ?)
                """,
                (
                    JobItemStatus.PENDING.value,
                    job_id,
                    JobItemStatus.RUNNING.value,
                    JobItemStatus.FAILED.value,
                ),
            )
            connection.execute(
                """
                UPDATE jobs SET status = ?, updated_at = ?, error = NULL
                WHERE id = ?
                """,
                (JobStatus.RUNNING.value, now, job_id),
            )
        return self.get_job(job_id)

    def mark_item_running(self, job_id: str, ordinal: int) -> None:
        self._update_item(
            job_id,
            ordinal,
            JobItemStatus.RUNNING,
            saved_candles=0,
            error=None,
        )

    def finish_item(
        self,
        job_id: str,
        ordinal: int,
        status: JobItemStatus,
        saved_candles: int,
        error: str | None = None,
    ) -> None:
        if status not in {
            JobItemStatus.SUCCEEDED,
            JobItemStatus.NO_DATA,
            JobItemStatus.FAILED,
        }:
            raise ValueError(f"Invalid terminal job-item status: {status.value}.")
        self._update_item(
            job_id,
            ordinal,
            status,
            saved_candles=saved_candles,
            error=error,
        )

    def finish_job(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> DownloadJob:
        if status not in {
            JobStatus.COMPLETED,
            JobStatus.COMPLETED_WITH_ERRORS,
            JobStatus.CANCELLED,
        }:
            raise ValueError(f"Invalid terminal job status: {status.value}.")
        with self._connection() as connection, connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, error = ?
                WHERE id = ?
                """,
                (status.value, _utc_now(), error, job_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Unknown download job: {job_id}")
        return self.get_job(job_id)

    def _update_item(
        self,
        job_id: str,
        ordinal: int,
        status: JobItemStatus,
        saved_candles: int,
        error: str | None,
    ) -> None:
        with self._connection() as connection, connection:
            cursor = connection.execute(
                """
                UPDATE job_items
                SET status = ?, saved_candles = ?, error = ?
                WHERE job_id = ? AND ordinal = ?
                """,
                (status.value, saved_candles, error, job_id, ordinal),
            )
            if cursor.rowcount == 0:
                raise KeyError(
                    f"Unknown item {ordinal} in download job {job_id}."
                )
            connection.execute(
                "UPDATE jobs SET updated_at = ? WHERE id = ?",
                (_utc_now(), job_id),
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_instrument(instrument: DataInstrument) -> dict[str, object]:
    if isinstance(instrument, OptionContract):
        return {
            "type": "option",
            "name": instrument.name,
            "instrument_key": instrument.instrument_key,
            "underlying_category": instrument.underlying_category,
            "underlying_slug": instrument.underlying_slug,
            "expiry_type": instrument.expiry_type,
            "expiry_date": instrument.expiry_date.isoformat(),
            "strike_price": instrument.strike_price,
            "option_type": instrument.option_type,
        }
    return {
        "type": "market",
        "name": instrument.name,
        "instrument_key": instrument.instrument_key,
        "category": instrument.category.value,
        "slug": instrument.slug,
        "tradingsymbol": instrument.tradingsymbol,
        "sector_slug": instrument.sector_slug,
        "legacy_slugs": list(instrument.legacy_slugs),
    }


def _deserialize_instrument(data: dict[str, object]) -> DataInstrument:
    if data["type"] == "option":
        return OptionContract(
            name=str(data["name"]),
            instrument_key=str(data["instrument_key"]),
            underlying_category=str(data["underlying_category"]),
            underlying_slug=str(data["underlying_slug"]),
            expiry_type=str(data["expiry_type"]),
            expiry_date=date.fromisoformat(str(data["expiry_date"])),
            strike_price=str(data["strike_price"]),
            option_type=str(data["option_type"]),
        )
    if data["type"] == "market":
        raw_legacy_slugs = data["legacy_slugs"]
        if not isinstance(raw_legacy_slugs, list) or not all(
            isinstance(slug, str) for slug in raw_legacy_slugs
        ):
            raise ValueError("Invalid legacy-slug data in the job database.")
        tradingsymbol = data["tradingsymbol"]
        sector_slug = data["sector_slug"]
        return MarketInstrument(
            name=str(data["name"]),
            instrument_key=str(data["instrument_key"]),
            category=InstrumentCategory(str(data["category"])),
            slug=str(data["slug"]),
            tradingsymbol=(
                str(tradingsymbol) if tradingsymbol is not None else None
            ),
            sector_slug=str(sector_slug) if sector_slug is not None else None,
            legacy_slugs=tuple(raw_legacy_slugs),
        )
    raise ValueError("Unknown instrument type in the job database.")
