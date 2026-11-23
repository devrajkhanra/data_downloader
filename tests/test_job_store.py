import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.job_models import JobItemStatus, JobStatus
from market_data_downloader.job_store import SQLiteJobStore
from market_data_downloader.models import OptionContract


class SQLiteJobStoreTests(unittest.TestCase):
    def test_persists_job_and_instrument_state(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "jobs.sqlite3"
            store = SQLiteJobStore(database_path)
            option = OptionContract(
                name="NIFTY 2026-12-31 26000 CE",
                instrument_key="NSE_FO|12345",
                underlying_category="indices",
                underlying_slug="nifty50",
                expiry_type="monthly",
                expiry_date=date(2026, 12, 31),
                strike_price="26000",
                option_type="CE",
            )
            job_id = store.create_job(
                (BROAD_INDICES[0], option),
                date(2026, 1, 1),
                date(2026, 11, 17),
                5,
            )

            snapshot = store.get_job(job_id)
            items = store.get_items(job_id)
            reopened_snapshot = SQLiteJobStore(database_path).get_job(job_id)

        self.assertEqual(snapshot.status, JobStatus.QUEUED)
        self.assertEqual(snapshot.total_items, 2)
        self.assertEqual(reopened_snapshot, snapshot)
        self.assertEqual(items[0].instrument, BROAD_INDICES[0])
        self.assertEqual(items[1].instrument, option)

    def test_failed_items_can_be_retried_and_crashed_jobs_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteJobStore(Path(directory) / "jobs.sqlite3")
            job_id = store.create_job(
                (BROAD_INDICES[0], BROAD_INDICES[1]),
                date(2026, 1, 1),
                date(2026, 11, 17),
                5,
            )
            store.start_job(job_id)
            store.mark_item_running(job_id, 0)
            store.finish_item(
                job_id,
                0,
                JobItemStatus.FAILED,
                0,
                "temporary API failure",
            )
            store.mark_item_running(job_id, 1)
            with self.assertRaises(RuntimeError):
                store.start_job(job_id)
            store.finish_job(
                job_id,
                JobStatus.COMPLETED_WITH_ERRORS,
                "temporary API failure",
            )

            resumed = store.start_job(job_id)
            pending = store.get_items(
                job_id,
                statuses=(JobItemStatus.PENDING,),
            )

        self.assertEqual(resumed.status, JobStatus.RUNNING)
        self.assertEqual(len(pending), 2)
        self.assertEqual(
            {item.status for item in pending},
            {JobItemStatus.PENDING},
        )

    def test_rejects_duplicate_instruments(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteJobStore(Path(directory) / "jobs.sqlite3")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                store.create_job(
                    (BROAD_INDICES[0], BROAD_INDICES[0]),
                    date(2026, 1, 1),
                    date(2026, 11, 17),
                    5,
                )

    def test_explicit_recovery_requeues_items_left_running_after_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteJobStore(Path(directory) / "jobs.sqlite3")
            job_id = store.create_job(
                (BROAD_INDICES[0], BROAD_INDICES[1]),
                date(2026, 1, 1),
                date(2026, 11, 17),
                5,
            )
            store.start_job(job_id)
            store.mark_item_running(job_id, 0)

            with self.assertRaises(RuntimeError):
                store.start_job(job_id)
            recovered = store.start_job(job_id, recover_running=True)
            pending = store.get_items(
                job_id,
                statuses=(JobItemStatus.PENDING,),
            )

        self.assertEqual(recovered.status, JobStatus.RUNNING)
        self.assertEqual(len(pending), 2)


if __name__ == "__main__":
    unittest.main()
