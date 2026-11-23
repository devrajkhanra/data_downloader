import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.download_engine import DownloadEngine
from market_data_downloader.job_models import JobItemStatus, JobStatus
from market_data_downloader.job_store import SQLiteJobStore
from market_data_downloader.models import InstrumentCategory, MarketInstrument
from market_data_downloader.upstox_client import UpstoxApiError


class SharedCallTracker:
    def __init__(self):
        self.active = 0
        self.maximum_active = 0
        self.lock = threading.Lock()


class FakeClient:
    def __init__(self, tracker, failures=None):
        self._tracker = tracker
        self._failures = failures if failures is not None else set()
        self.calls = []

    def get_historical_candles(
        self,
        instrument_key,
        start_date,
        end_date,
        interval_minutes,
    ):
        self.calls.append(
            (instrument_key, start_date, end_date, interval_minutes)
        )
        with self._tracker.lock:
            self._tracker.active += 1
            self._tracker.maximum_active = max(
                self._tracker.maximum_active,
                self._tracker.active,
            )
        try:
            time.sleep(0.01)
            if instrument_key in self._failures:
                self._failures.remove(instrument_key)
                raise UpstoxApiError("Rate limited", status_code=429)
            return [
                [
                    "2026-10-27T09:15:00+05:30",
                    1,
                    2,
                    0,
                    1,
                    10,
                    0,
                ]
            ]
        finally:
            with self._tracker.lock:
                self._tracker.active -= 1


def instruments(count):
    return tuple(
        MarketInstrument(
            name=f"Test index {index}",
            instrument_key=f"NSE_INDEX|TEST{index}",
            category=InstrumentCategory.BROAD,
            slug=f"test-index-{index}",
        )
        for index in range(count)
    )


class DownloadEngineTests(unittest.TestCase):
    def test_downloads_concurrently_with_a_bounded_worker_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracker = SharedCallTracker()
            store = SQLiteJobStore(root / "jobs.sqlite3")
            engine = DownloadEngine(
                root / "data",
                store,
                lambda: FakeClient(tracker),
                max_workers=3,
            )
            job_id = engine.create_job(
                instruments(8),
                date(2026, 10, 27),
                date(2026, 10, 27),
            )
            progress = []

            job = engine.run_job(job_id, on_progress=progress.append)

        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.succeeded_items, 8)
        self.assertGreaterEqual(tracker.maximum_active, 2)
        self.assertLessEqual(tracker.maximum_active, 3)
        self.assertEqual(len(progress), 8)
        self.assertEqual(progress[-1].completed_items, 8)

    def test_api_wide_failure_leaves_work_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failures = {"NSE_INDEX|TEST0"}
            store = SQLiteJobStore(root / "jobs.sqlite3")
            engine = DownloadEngine(
                root / "data",
                store,
                lambda: FakeClient(SharedCallTracker(), failures),
                max_workers=1,
            )
            job_id = engine.create_job(
                instruments(3),
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            failed = engine.run_job(job_id)
            self.assertEqual(failed.status, JobStatus.COMPLETED_WITH_ERRORS)
            self.assertEqual(failed.failed_items, 1)
            self.assertEqual(failed.pending_items, 2)

            resumed = engine.resume_job(job_id)

        self.assertEqual(resumed.status, JobStatus.COMPLETED)
        self.assertEqual(resumed.succeeded_items, 3)
        self.assertEqual(resumed.pending_items, 0)

    def test_cancellation_keeps_unstarted_items_pending_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SQLiteJobStore(root / "jobs.sqlite3")
            engine = DownloadEngine(
                root / "data",
                store,
                lambda: FakeClient(SharedCallTracker()),
                max_workers=1,
            )
            job_id = engine.create_job(
                instruments(3),
                date(2026, 10, 27),
                date(2026, 10, 27),
            )
            cancel_event = threading.Event()
            cancel_event.set()

            cancelled = engine.run_job(job_id, cancel_event=cancel_event)
            pending = store.get_items(
                job_id,
                statuses=(JobItemStatus.PENDING,),
            )

        self.assertEqual(cancelled.status, JobStatus.CANCELLED)
        self.assertEqual(cancelled.pending_items, 3)
        self.assertEqual(len(pending), 3)

    def test_cancellation_stops_scheduling_and_can_resume_remaining_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SQLiteJobStore(root / "jobs.sqlite3")
            engine = DownloadEngine(
                root / "data",
                store,
                lambda: FakeClient(SharedCallTracker()),
                max_workers=1,
            )
            job_id = engine.create_job(
                instruments(3),
                date(2026, 10, 27),
                date(2026, 10, 27),
            )
            cancel_event = threading.Event()

            def cancel_after_first_item(progress):
                if progress.completed_items == 1:
                    cancel_event.set()

            cancelled = engine.run_job(
                job_id,
                on_progress=cancel_after_first_item,
                cancel_event=cancel_event,
            )
            resumed = engine.resume_job(job_id)

        self.assertEqual(cancelled.status, JobStatus.CANCELLED)
        self.assertEqual(cancelled.succeeded_items, 1)
        self.assertEqual(cancelled.pending_items, 2)
        self.assertEqual(resumed.status, JobStatus.COMPLETED)
        self.assertEqual(resumed.succeeded_items, 3)


if __name__ == "__main__":
    unittest.main()
