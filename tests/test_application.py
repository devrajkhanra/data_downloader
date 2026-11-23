import tempfile
import unittest
from datetime import date
from pathlib import Path

from market_data_downloader.application import DownloadApplication
from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.job_models import JobStatus


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date, date, int]] = []

    def get_historical_candles(
        self,
        instrument_key: str,
        start_date: date,
        end_date: date,
        interval_minutes: int = 5,
    ) -> list[list[str | int | float | None]]:
        self.calls.append(
            (instrument_key, start_date, end_date, interval_minutes)
        )
        return [
            [
                f"{start_date.isoformat()}T09:15:00+05:30",
                1,
                2,
                0,
                1,
                10,
                0,
            ]
        ]

    def close(self) -> None:
        pass


class DownloadApplicationTests(unittest.TestCase):
    def test_composes_download_engine_with_overridable_paths_and_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = DownloadApplication(
                data_root=root / "data",
                job_database_path=root / "jobs.sqlite3",
            )
            tokens: list[str] = []
            clients: list[FakeClient] = []

            def create_client(token: str) -> FakeClient:
                tokens.append(token)
                client = FakeClient()
                clients.append(client)
                return client

            job_store = application.create_job_store()
            engine = application.create_download_engine(
                "test-token",
                max_workers=1,
                job_store=job_store,
                client_factory=create_client,
            )
            job_id = engine.create_job(
                (BROAD_INDICES[0],),
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

            job = engine.run_job(job_id)
            candles = application.create_market_data_repository().load_candles(
                BROAD_INDICES[0]
            )

        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(tokens, ["test-token"])
        self.assertEqual(len(candles), 1)
        self.assertEqual(
            clients[0].calls,
            [
                (
                    BROAD_INDICES[0].instrument_key,
                    date(2026, 10, 27),
                    date(2026, 10, 27),
                    5,
                )
            ],
        )

    def test_rejects_empty_token_before_creating_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            application = DownloadApplication(
                data_root=Path(directory) / "data",
                job_database_path=Path(directory) / "jobs.sqlite3",
            )

            with self.assertRaisesRegex(ValueError, "Access token is required"):
                application.create_download_engine(" ")


if __name__ == "__main__":
    unittest.main()
