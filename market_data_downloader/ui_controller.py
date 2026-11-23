import sqlite3
from dataclasses import dataclass
from datetime import date
from threading import Event

from PySide6.QtCore import Property, QObject, QThread, Signal, Slot

from market_data_downloader.application import DownloadApplication
from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.date_ranges import parse_iso_date
from market_data_downloader.download_engine import DEFAULT_MAX_WORKERS
from market_data_downloader.job_models import (
    DownloadJob,
    DownloadProgress,
    JobStatus,
)
from market_data_downloader.models import (
    DataInstrument,
    InstrumentCategory,
    MarketInstrument,
)
from market_data_downloader.nse_industries import (
    StockIndustryLookupError,
    count_uncached_industries,
)
from market_data_downloader.option_catalog import OptionCatalogError, load_option_contracts
from market_data_downloader.stock_catalog import (
    EQUITY_LIST_PATH,
    InstrumentMasterError,
    load_nse_stocks,
)
from market_data_downloader.stock_service import prepare_stock_instruments


@dataclass(frozen=True)
class PreparedDownload:
    instruments: tuple[DataInstrument, ...]
    stocks: tuple[MarketInstrument, ...]
    stale_list_warnings: tuple[str, ...]
    uncached_sector_count: int
    option_count: int


class CatalogTask(QThread):
    loaded = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)

    def __init__(
        self,
        selected_keys: tuple[str, ...],
        application: DownloadApplication,
    ) -> None:
        super().__init__()
        self._selected_keys = set(selected_keys)
        self._application = application

    def run(self) -> None:
        try:
            application = self._application
            self.status_changed.emit("Loading selected instruments...")
            instruments: list[DataInstrument] = [
                instrument
                for instrument in ALL_INDICES
                if instrument.instrument_key in self._selected_keys
            ]
            stocks: tuple[MarketInstrument, ...] = ()
            stale_warnings: list[str] = []
            uncached_sector_count = 0
            option_count = 0

            if "stocks" in self._selected_keys:
                self.status_changed.emit("Refreshing the NSE equity list...")
                stock_catalog = load_nse_stocks()
                stocks = stock_catalog.instruments
                instruments.extend(stocks)
                if stock_catalog.equity_list_warning:
                    stale_warnings.append(
                        f"The NSE list could not be refreshed "
                        f"({stock_catalog.equity_list_warning}). The saved "
                        f"{EQUITY_LIST_PATH.name} will be used."
                    )
                uncached_sector_count = count_uncached_industries(
                    stocks,
                    application.data_root / ".stock_industry_cache.json",
                )

            if "options" in self._selected_keys:
                self.status_changed.emit("Loading currently listed options...")
                option_catalog = load_option_contracts()
                instruments.extend(option_catalog.contracts)
                option_count = len(option_catalog.contracts)
                if option_catalog.equity_list_warning:
                    stale_warnings.append(
                        f"The NSE list used for option discovery could not be "
                        f"refreshed ({option_catalog.equity_list_warning}). "
                        f"The saved {EQUITY_LIST_PATH.name} will be used."
                    )

            if not instruments:
                if "options" in self._selected_keys:
                    raise ValueError("No currently listed option contracts were found.")
                raise ValueError("Select at least one instrument or data category.")
            if len({item.instrument_key for item in instruments}) != len(instruments):
                raise ValueError("The selected catalogs contain duplicate instruments.")

            self.loaded.emit(
                PreparedDownload(
                    instruments=tuple(instruments),
                    stocks=stocks,
                    stale_list_warnings=tuple(stale_warnings),
                    uncached_sector_count=uncached_sector_count,
                    option_count=option_count,
                )
            )
        except (
            InstrumentMasterError,
            OptionCatalogError,
            StockIndustryLookupError,
            OSError,
            ValueError,
        ) as exc:
            self.failed.emit(str(exc))


class DownloadTask(QThread):
    progress = Signal(object)
    status_changed = Signal(str)
    cancel_enabled = Signal(bool)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        token: str,
        max_workers: int,
        *,
        prepared: PreparedDownload | None = None,
        first_download_date: date | None = None,
        end_date: date | None = None,
        resume_job_id: str | None = None,
        application: DownloadApplication | None = None,
    ) -> None:
        super().__init__()
        self._application = (
            application if application is not None else DownloadApplication()
        )
        self._token = token
        self._max_workers = max_workers
        self._prepared = prepared
        self._first_download_date = first_download_date
        self._end_date = end_date
        self._resume_job_id = resume_job_id
        self.cancel_event = Event()

    def run(self) -> None:
        try:
            application = self._application
            job_store = application.create_job_store()
            engine = application.create_download_engine(
                self._token,
                max_workers=self._max_workers,
                job_store=job_store,
            )
            if self._resume_job_id is not None:
                self.status_changed.emit("Resuming saved download job...")
                self.cancel_enabled.emit(True)
                job = engine.resume_job(
                    self._resume_job_id,
                    on_progress=self.progress.emit,
                    cancel_event=self.cancel_event,
                )
            else:
                prepared = self._prepared
                if prepared is None or self._end_date is None:
                    raise RuntimeError("The download request is incomplete.")

                instruments = list(prepared.instruments)
                if prepared.stocks:
                    self.status_changed.emit(
                        f"Looking up NSE sectors for {len(prepared.stocks):,} stocks..."
                    )

                    def report_sector_progress(
                        completed: int,
                        total: int,
                        stock: MarketInstrument,
                    ) -> None:
                        self.progress.emit(
                            {
                                "phase": "sectors",
                                "completed": completed,
                                "total": total,
                                "instrument": stock.tradingsymbol or stock.name,
                            }
                        )

                    classified_stocks = prepare_stock_instruments(
                        prepared.stocks,
                        application.data_root,
                        on_progress=report_sector_progress,
                    )
                    instruments = [
                        instrument
                        for instrument in instruments
                        if not (
                            isinstance(instrument, MarketInstrument)
                            and instrument.category is InstrumentCategory.STOCKS
                        )
                    ]
                    instruments.extend(classified_stocks)

                repository = application.create_market_data_repository()
                missing_count = sum(
                    repository.latest_date(instrument) is None
                    for instrument in instruments
                )
                if missing_count and self._first_download_date is None:
                    raise ValueError(
                        f"{missing_count:,} selected instrument(s) have no CSV "
                        "data yet. Enter an initial start date and try again."
                    )

                job_id = engine.create_job(
                    tuple(instruments),
                    self._first_download_date,
                    self._end_date,
                )
                self.status_changed.emit(
                    f"Downloading {len(instruments):,} instrument(s)..."
                )
                self.cancel_enabled.emit(True)
                job = engine.run_job(
                    job_id,
                    on_progress=self.progress.emit,
                    cancel_event=self.cancel_event,
                )

            self.completed.emit(job)
        except (
            InstrumentMasterError,
            StockIndustryLookupError,
            OSError,
            ValueError,
            RuntimeError,
            KeyError,
            sqlite3.Error,
        ) as exc:
            self.failed.emit(str(exc))
        finally:
            self.cancel_enabled.emit(False)


class DownloadController(QObject):
    busyChanged = Signal()
    selectedKeysChanged = Signal()
    selectedCountChanged = Signal()
    broadChoicesChanged = Signal()
    sectorChoicesChanged = Signal()
    recentJobsChanged = Signal()
    selectedJobIdChanged = Signal()
    progressValueChanged = Signal()
    statusMessageChanged = Signal()
    statusKindChanged = Signal()
    canCancelChanged = Signal()
    canResumeChanged = Signal()
    confirmationRequested = Signal(str)

    def __init__(
        self,
        application: DownloadApplication | None = None,
    ) -> None:
        super().__init__()
        self._application = (
            application if application is not None else DownloadApplication()
        )
        self._selected_keys: set[str] = set()
        self._busy = False
        self._can_cancel = False
        self._recent_jobs: list[dict[str, object]] = []
        self._selected_job_id = ""
        self._progress_value = 0.0
        self._status_message = "Choose data to download."
        self._status_kind = "info"
        self._access_token = ""
        self._first_download_date: date | None = None
        self._end_date: date | None = None
        self._max_workers = DEFAULT_MAX_WORKERS
        self._prepared: PreparedDownload | None = None
        self._catalog_task: CatalogTask | None = None
        self._download_task: DownloadTask | None = None
        self._pending_finish: tuple[str, str] | None = None
        self._pending_task: QThread | None = None
        self._broad_choices = [
            {"key": item.instrument_key, "name": item.name}
            for item in BROAD_INDICES
        ]
        self._sector_choices = [
            {"key": item.instrument_key, "name": item.name}
            for item in SECTORAL_INDICES
        ]
        self.refreshJobs()

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property("QStringList", notify=selectedKeysChanged)
    def selectedKeys(self) -> list[str]:
        return sorted(self._selected_keys)

    @Property(int, notify=selectedCountChanged)
    def selectedCount(self) -> int:
        return len(self._selected_keys)

    @Property("QVariantList", notify=broadChoicesChanged)
    def broadChoices(self) -> list[dict[str, str]]:
        return self._broad_choices

    @Property("QVariantList", notify=sectorChoicesChanged)
    def sectorChoices(self) -> list[dict[str, str]]:
        return self._sector_choices

    @Property("QVariantList", notify=recentJobsChanged)
    def recentJobs(self) -> list[dict[str, object]]:
        return self._recent_jobs

    @Property(str, notify=selectedJobIdChanged)
    def selectedJobId(self) -> str:
        return self._selected_job_id

    @Property(float, notify=progressValueChanged)
    def progressValue(self) -> float:
        return self._progress_value

    @Property(str, notify=statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=statusKindChanged)
    def statusKind(self) -> str:
        return self._status_kind

    @Property(bool, notify=canCancelChanged)
    def canCancel(self) -> bool:
        return self._can_cancel

    @Property(bool, notify=canResumeChanged)
    def canResume(self) -> bool:
        job = self._find_selected_job()
        return (
            not self._busy
            and bool(job)
            and job["status"] != JobStatus.COMPLETED.value
        )

    @Slot(str, bool)
    def setSelected(self, key: str, selected: bool) -> None:
        known_keys = {
            instrument.instrument_key for instrument in ALL_INDICES
        } | {"stocks", "options"}
        if self._busy or key not in known_keys:
            return
        updated_keys = set(self._selected_keys)
        if selected:
            updated_keys.add(key)
        else:
            updated_keys.discard(key)
        if updated_keys == self._selected_keys:
            return
        self._selected_keys = updated_keys
        self.selectedKeysChanged.emit()
        self.selectedCountChanged.emit()

    @Slot(str, str, str, int)
    def startDownload(
        self,
        token: str,
        initial_start_date: str,
        end_date_text: str,
        max_workers: int,
    ) -> None:
        if self._busy:
            return
        if not self._selected_keys:
            self._set_status("Select at least one instrument or data category.", "error")
            return
        if not token.strip():
            self._set_status("Enter your Upstox access token.", "error")
            return
        if not 1 <= max_workers <= 8:
            self._set_status("Worker count must be between 1 and 8.", "error")
            return
        try:
            end_date = parse_iso_date(end_date_text.strip())
            if end_date > date.today():
                raise ValueError("End date cannot be in the future.")
            start_date = (
                parse_iso_date(initial_start_date.strip())
                if initial_start_date.strip()
                else None
            )
            if start_date is not None and start_date > end_date:
                raise ValueError("Initial start date cannot be after the end date.")
        except ValueError as exc:
            self._set_status(str(exc), "error")
            return

        self._access_token = token.strip()
        self._first_download_date = start_date
        self._end_date = end_date
        self._max_workers = max_workers
        self._prepared = None
        self._set_busy(True)
        self._set_progress(0.0)
        self._set_status("Preparing the selected data catalogs...", "info")

        task = CatalogTask(tuple(self._selected_keys), self._application)
        task.status_changed.connect(self._on_task_status)
        task.loaded.connect(self._on_catalog_loaded)
        task.failed.connect(self._on_catalog_task_failed)
        task.finished.connect(
            lambda task=task: self._on_catalog_thread_finished(task)
        )
        self._catalog_task = task
        task.start()

    @Slot(bool)
    def confirmPreparation(self, accepted: bool) -> None:
        if not self._busy or self._prepared is None:
            return
        if not accepted:
            self._complete_after_task(
                "Download setup cancelled.",
                "info",
                self._catalog_task,
            )
            return
        self._start_download()

    @Slot()
    def cancelDownload(self) -> None:
        task = self._download_task
        if task is None or not self._can_cancel:
            return
        task.cancel_event.set()
        self._set_status(
            "Cancellation requested; active API requests will finish first.",
            "warning",
        )

    @Slot(str)
    def selectJob(self, job_id: str) -> None:
        if job_id == self._selected_job_id:
            return
        if not any(job["jobId"] == job_id for job in self._recent_jobs):
            return
        self._selected_job_id = job_id
        self.selectedJobIdChanged.emit()
        self.canResumeChanged.emit()

    @Slot(str)
    def resumeJob(self, token: str) -> None:
        if self._busy:
            return
        job = self._find_selected_job()
        if job is None:
            self._set_status("Select a saved job to resume.", "error")
            return
        if job["status"] == JobStatus.COMPLETED.value:
            self._set_status("That download job is already complete.", "error")
            return
        if not token.strip():
            self._set_status("Enter your Upstox access token to resume.", "error")
            return

        self._access_token = token.strip()
        self._max_workers = DEFAULT_MAX_WORKERS
        self._set_busy(True)
        self._set_progress(
            job["completedItems"] / max(1, job["totalItems"])
        )
        self._set_status(f"Resuming job {self._selected_job_id}...", "info")
        task = DownloadTask(
            self._access_token,
            self._max_workers,
            resume_job_id=self._selected_job_id,
            application=self._application,
        )
        task.progress.connect(self._on_download_progress)
        task.status_changed.connect(self._on_task_status)
        task.cancel_enabled.connect(self._set_can_cancel)
        task.completed.connect(self._on_download_completed)
        task.failed.connect(self._on_download_task_failed)
        task.finished.connect(
            lambda task=task: self._on_download_thread_finished(task)
        )
        self._download_task = task
        task.start()

    @Slot()
    def refreshJobs(self) -> None:
        try:
            jobs = self._application.create_job_store().list_jobs(25)
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            self._set_status(f"Could not load saved jobs: {exc}", "error")
            return

        self._recent_jobs = [
            {
                "jobId": job.job_id,
                "status": job.status.value.replace("_", " "),
                "statusCode": job.status.value,
                "createdAt": job.created_at.astimezone().strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "completedItems": job.completed_items,
                "totalItems": job.total_items,
                "succeededItems": job.succeeded_items,
                "noDataItems": job.no_data_items,
                "failedItems": job.failed_items,
                "summary": (
                    f"{job.completed_items:,}/{job.total_items:,} items"
                    f" · {job.succeeded_items:,} saved"
                    f" · {job.failed_items:,} failed"
                ),
            }
            for job in jobs
        ]
        if self._selected_job_id and not any(
            job["jobId"] == self._selected_job_id for job in self._recent_jobs
        ):
            self._selected_job_id = ""
            self.selectedJobIdChanged.emit()
        self.recentJobsChanged.emit()
        self.canResumeChanged.emit()

    def _on_catalog_loaded(self, prepared: PreparedDownload) -> None:
        self._prepared = prepared
        warnings = list(prepared.stale_list_warnings)
        if prepared.stocks:
            warnings.append(
                f"{len(prepared.stocks):,} NSE stocks are selected. "
                "Their sectors may need a slow refresh, and downloading them "
                "can use substantial API quota and disk space."
            )
            if prepared.uncached_sector_count:
                warnings.append(
                    f"{prepared.uncached_sector_count:,} stock sector lookup(s) "
                    "are missing or stale."
                )
        if prepared.option_count:
            warnings.append(
                f"{prepared.option_count:,} currently listed option contracts "
                "are selected across all strikes and expiries. This may take a "
                "long time and use substantial API quota and disk space."
            )
        if warnings:
            self.confirmationRequested.emit("\n\n".join(warnings))
        else:
            self._start_download()

    def _start_download(self) -> None:
        prepared = self._prepared
        if prepared is None:
            return
        task = DownloadTask(
            self._access_token,
            self._max_workers,
            prepared=prepared,
            first_download_date=self._first_download_date,
            end_date=self._end_date,
            application=self._application,
        )
        task.progress.connect(self._on_download_progress)
        task.status_changed.connect(self._on_task_status)
        task.cancel_enabled.connect(self._set_can_cancel)
        task.completed.connect(self._on_download_completed)
        task.failed.connect(self._on_download_task_failed)
        task.finished.connect(
            lambda task=task: self._on_download_thread_finished(task)
        )
        self._download_task = task
        task.start()

    @Slot(object)
    def _on_download_progress(self, progress: object) -> None:
        if isinstance(progress, DownloadProgress):
            self._set_progress(
                progress.completed_items / max(1, progress.total_items)
            )
            message = (
                f"{progress.completed_items:,}/{progress.total_items:,} complete"
                f" · {progress.instrument_name}"
                f" · {progress.item_status.value.replace('_', ' ')}"
            )
            if progress.error:
                message += f" · {progress.error}"
            self._set_status(message, "warning" if progress.error else "info")
        elif isinstance(progress, dict) and progress.get("phase") == "sectors":
            completed = progress["completed"]
            total = progress["total"]
            self._set_progress(completed / max(1, total))
            self._set_status(
                f"Sector lookup {completed:,}/{total:,} · "
                f"{progress['instrument']}",
                "info",
            )

    @Slot(str)
    def _on_task_status(self, message: str) -> None:
        self._set_status(message, "info")

    @Slot(str)
    def _on_catalog_task_failed(self, message: str) -> None:
        self._complete_after_task(message, "error", self._catalog_task)

    def _on_download_task_failed(self, message: str) -> None:
        self.refreshJobs()
        self._complete_after_task(message, "error", self._download_task)

    @Slot(object)
    def _on_download_completed(self, job: object) -> None:
        if not isinstance(job, DownloadJob):
            self._complete_after_task(
                "The download task returned an invalid job result.",
                "error",
                self._download_task,
            )
            return
        self.refreshJobs()
        self._selected_job_id = job.job_id
        self.selectedJobIdChanged.emit()
        if job.status is JobStatus.COMPLETED:
            message = (
                f"Download complete · {job.succeeded_items:,} saved, "
                f"{job.no_data_items:,} with no new candles."
            )
            kind = "success"
            self._set_progress(1.0)
        elif job.status is JobStatus.CANCELLED:
            message = (
                f"Job cancelled · {job.completed_items:,}/{job.total_items:,} "
                "items finished. Resume it from Job history."
            )
            kind = "warning"
        else:
            message = (
                f"Job finished with errors · {job.failed_items:,} failed, "
                f"{job.pending_items:,} remaining. Resume it from Job history."
            )
            if job.error:
                message += f" · {job.error}"
            kind = "warning"
        self._complete_after_task(message, kind, self._download_task)

    def _on_catalog_thread_finished(self, task: CatalogTask) -> None:
        if self._catalog_task is task:
            self._catalog_task = None
        self._finish_if_task_completed(task)

    def _on_download_thread_finished(self, task: DownloadTask) -> None:
        if self._download_task is task:
            self._download_task = None
        self._finish_if_task_completed(task)

    def _complete_after_task(
        self,
        message: str,
        kind: str,
        task: QThread | None,
    ) -> None:
        if task is None or not task.isRunning():
            self._finish_operation(message, kind)
            return
        self._pending_finish = (message, kind)
        self._pending_task = task

    def _finish_if_task_completed(self, task: QThread) -> None:
        if task is not self._pending_task or self._pending_finish is None:
            return
        message, kind = self._pending_finish
        self._pending_finish = None
        self._pending_task = None
        self._finish_operation(message, kind)

    def _find_selected_job(self) -> dict[str, object] | None:
        return next(
            (
                job
                for job in self._recent_jobs
                if job["jobId"] == self._selected_job_id
            ),
            None,
        )

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busyChanged.emit()
        self.canResumeChanged.emit()

    def _set_can_cancel(self, can_cancel: bool) -> None:
        if self._can_cancel == can_cancel:
            return
        self._can_cancel = can_cancel
        self.canCancelChanged.emit()

    def _set_progress(self, progress: float) -> None:
        value = min(1.0, max(0.0, progress))
        if self._progress_value == value:
            return
        self._progress_value = value
        self.progressValueChanged.emit()

    def _set_status(self, message: str, kind: str) -> None:
        if self._status_message != message:
            self._status_message = message
            self.statusMessageChanged.emit()
        if self._status_kind != kind:
            self._status_kind = kind
            self.statusKindChanged.emit()

    def _finish_operation(self, message: str, kind: str) -> None:
        self._set_can_cancel(False)
        self._set_busy(False)
        self._pending_finish = None
        self._pending_task = None
        self._access_token = ""
        self._first_download_date = None
        self._end_date = None
        self._prepared = None
        self._set_status(message, kind)
