from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Event, Lock, local
from typing import Callable

from market_data_downloader.data_repository import (
    CsvMarketDataRepository,
    MarketDataRepository,
)
from market_data_downloader.downloader import (
    HistoricalDataSource,
    download_instrument,
    next_start_date,
)
from market_data_downloader.job_models import (
    DownloadJob,
    DownloadJobItem,
    DownloadProgress,
    JobItemStatus,
    JobStatus,
)
from market_data_downloader.job_store import DownloadJobStore
from market_data_downloader.models import DataInstrument
from market_data_downloader.upstox_client import UpstoxApiError


DEFAULT_MAX_WORKERS = 3
MAX_ALLOWED_WORKERS = 8
ProgressCallback = Callable[[DownloadProgress], None]
ClientFactory = Callable[[], HistoricalDataSource]


@dataclass(frozen=True)
class _ItemOutcome:
    status: JobItemStatus
    saved_candles: int = 0
    error: str | None = None
    stop_job: bool = False


class DownloadEngine:
    """Bounded, resumable orchestration for historical market-data jobs."""

    def __init__(
        self,
        data_root: Path,
        job_store: DownloadJobStore,
        client_factory: ClientFactory,
        *,
        repository: MarketDataRepository | None = None,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        if not 1 <= max_workers <= MAX_ALLOWED_WORKERS:
            raise ValueError(
                f"Worker count must be between 1 and {MAX_ALLOWED_WORKERS}."
            )
        self._data_root = data_root
        self._jobs = job_store
        self._client_factory = client_factory
        self._repository = (
            repository
            if repository is not None
            else CsvMarketDataRepository(data_root)
        )
        self._max_workers = max_workers
        self._client_context = local()
        self._clients: list[HistoricalDataSource] = []
        self._clients_lock = Lock()
        self._active_jobs: set[str] = set()
        self._active_jobs_lock = Lock()

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def create_job(
        self,
        instruments: tuple[DataInstrument, ...],
        first_download_date: date | None,
        end_date: date,
        interval_minutes: int = 5,
    ) -> str:
        return self._jobs.create_job(
            instruments,
            first_download_date,
            end_date,
            interval_minutes,
        )

    def get_job(self, job_id: str) -> DownloadJob:
        return self._jobs.get_job(job_id)

    def list_jobs(self, limit: int = 50) -> tuple[DownloadJob, ...]:
        return self._jobs.list_jobs(limit)

    def run_job(
        self,
        job_id: str,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> DownloadJob:
        return self._run_job(
            job_id,
            recover_running=False,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

    def resume_job(
        self,
        job_id: str,
        *,
        on_progress: ProgressCallback | None = None,
        cancel_event: Event | None = None,
    ) -> DownloadJob:
        """Resume unfinished work, retrying failed items and recovering crashes."""
        return self._run_job(
            job_id,
            recover_running=True,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )

    def _run_job(
        self,
        job_id: str,
        *,
        recover_running: bool,
        on_progress: ProgressCallback | None,
        cancel_event: Event | None,
    ) -> DownloadJob:
        with self._active_jobs_lock:
            if self._active_jobs:
                active_job_id = next(iter(self._active_jobs))
                raise RuntimeError(
                    f"Download engine is already running job {active_job_id}."
                )
            self._active_jobs.add(job_id)

        try:
            job = self._jobs.start_job(job_id, recover_running=recover_running)
            items = self._jobs.get_items(
                job_id,
                statuses=(JobItemStatus.PENDING,),
            )
            return self._execute_job(
                job,
                items,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
        finally:
            with self._active_jobs_lock:
                self._active_jobs.remove(job_id)

    def _execute_job(
        self,
        job: DownloadJob,
        items: tuple[DownloadJobItem, ...],
        *,
        on_progress: ProgressCallback | None,
        cancel_event: Event | None,
    ) -> DownloadJob:
        item_iterator = iter(items)
        running: dict[Future[_ItemOutcome], DownloadJobItem] = {}
        stop_error: str | None = None
        effective_cancel = cancel_event if cancel_event is not None else Event()
        interrupted = False
        succeeded_count = job.succeeded_items
        no_data_count = job.no_data_items
        failed_count = job.failed_items

        def submit_available(executor: ThreadPoolExecutor) -> None:
            while (
                len(running) < self._max_workers
                and stop_error is None
                and not effective_cancel.is_set()
            ):
                item = next(item_iterator, None)
                if item is None:
                    return
                self._jobs.mark_item_running(job.job_id, item.ordinal)
                future = executor.submit(self._download_item, job, item)
                running[future] = item

        try:
            with ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="market-data",
            ) as executor:
                submit_available(executor)
                while running:
                    try:
                        completed, _ = wait(
                            running,
                            return_when=FIRST_COMPLETED,
                        )
                    except KeyboardInterrupt:
                        effective_cancel.set()
                        interrupted = True
                        continue
                    for future in completed:
                        item = running.pop(future)
                        outcome = future.result()
                        self._jobs.finish_item(
                            job.job_id,
                            item.ordinal,
                            outcome.status,
                            outcome.saved_candles,
                            outcome.error,
                        )
                        if outcome.status is JobItemStatus.SUCCEEDED:
                            succeeded_count += 1
                        elif outcome.status is JobItemStatus.NO_DATA:
                            no_data_count += 1
                        else:
                            failed_count += 1
                        if outcome.stop_job and stop_error is None:
                            stop_error = outcome.error
                        if on_progress is not None:
                            on_progress(
                                DownloadProgress(
                                    job_id=job.job_id,
                                    completed_items=(
                                        succeeded_count
                                        + no_data_count
                                        + failed_count
                                    ),
                                    total_items=job.total_items,
                                    succeeded_items=succeeded_count,
                                    no_data_items=no_data_count,
                                    failed_items=failed_count,
                                    active_items=sum(
                                        not active_future.done()
                                        for active_future in running
                                    ),
                                    instrument_name=item.instrument.name,
                                    item_status=outcome.status,
                                    saved_candles=outcome.saved_candles,
                                    error=outcome.error,
                                )
                            )

                    submit_available(executor)
        finally:
            self._close_clients()

        snapshot = self._jobs.get_job(job.job_id)
        was_cancelled = interrupted or effective_cancel.is_set()
        if was_cancelled:
            status = JobStatus.CANCELLED
            error = "Cancellation requested; unfinished items can be resumed."
        elif (
            stop_error is not None
            or snapshot.pending_items
            or snapshot.failed_items
        ):
            status = JobStatus.COMPLETED_WITH_ERRORS
            error = stop_error
        else:
            status = JobStatus.COMPLETED
            error = None
        return self._jobs.finish_job(job.job_id, status, error)

    def _download_item(
        self,
        job: DownloadJob,
        item: DownloadJobItem,
    ) -> _ItemOutcome:
        try:
            start_date = next_start_date(
                self._data_root,
                item.instrument,
                job.first_download_date,
                repository=self._repository,
            )
            if start_date > job.end_date:
                return _ItemOutcome(JobItemStatus.NO_DATA)

            client = self._client_for_thread()
            saved = download_instrument(
                client,
                self._data_root,
                item.instrument,
                start_date,
                job.end_date,
                interval_minutes=job.interval_minutes,
                repository=self._repository,
            )
            status = (
                JobItemStatus.SUCCEEDED if saved else JobItemStatus.NO_DATA
            )
            return _ItemOutcome(status, saved_candles=saved)
        except UpstoxApiError as exc:
            stop_job = (
                exc.status_code is None
                or exc.status_code in {401, 403, 429}
                or exc.status_code >= 500
            )
            return _ItemOutcome(
                JobItemStatus.FAILED,
                error=str(exc),
                stop_job=stop_job,
            )
        except (OSError, ValueError) as exc:
            return _ItemOutcome(
                JobItemStatus.FAILED,
                error=str(exc),
            )

    def _client_for_thread(self) -> HistoricalDataSource:
        client = getattr(self._client_context, "client", None)
        if client is None:
            client = self._client_factory()
            self._client_context.client = client
            with self._clients_lock:
                self._clients.append(client)
        return client

    def _close_clients(self) -> None:
        with self._clients_lock:
            clients = tuple(self._clients)
            self._clients.clear()
        for client in clients:
            close = getattr(client, "close", None)
            if callable(close):
                close()
