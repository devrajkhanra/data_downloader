from contextlib import contextmanager
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

from PySide6.QtCore import Q_ARG, QMetaObject, Qt

from market_data_downloader.application import DownloadApplication
from market_data_downloader.catalog import BROAD_INDICES
from market_data_downloader.ui_controller import DownloadController


@contextmanager
def _controller() -> Generator[DownloadController, None, None]:
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        application = DownloadApplication(
            data_root=root / "data",
            job_database_path=root / "download_jobs.sqlite3",
        )
        yield DownloadController(application)


def test_instrument_selection_updates_state() -> None:
    with _controller() as controller:
        key = BROAD_INDICES[0].instrument_key

        controller.setSelected(key, True)

        assert controller.selectedCount == 1
        assert controller.selectedKeys == [key]

        controller.setSelected(key, False)

        assert controller.selectedCount == 0
        assert controller.selectedKeys == []


def test_start_download_requires_access_token() -> None:
    with _controller() as controller:
        controller.setSelected(BROAD_INDICES[0].instrument_key, True)

        controller.startDownload("", "", date.today().isoformat(), 3)

        assert controller.statusMessage == "Enter your Upstox access token."
        assert not controller.busy


def test_start_date_cannot_be_after_end_date() -> None:
    with _controller() as controller:
        controller.setSelected(BROAD_INDICES[0].instrument_key, True)

        controller.startDownload("token", "2020-01-02", "2020-01-01", 3)

        assert (
            controller.statusMessage
            == "Initial start date cannot be after the end date."
        )
        assert not controller.busy


def test_qml_start_download_slot_accepts_four_arguments() -> None:
    with _controller() as controller:
        controller.setSelected(BROAD_INDICES[0].instrument_key, True)

        invoked = QMetaObject.invokeMethod(
            controller,
            "startDownload",
            Qt.DirectConnection,
            Q_ARG(str, ""),
            Q_ARG(str, ""),
            Q_ARG(str, date.today().isoformat()),
            Q_ARG(int, 3),
        )

        assert invoked
        assert controller.statusMessage == "Enter your Upstox access token."
        assert not controller.busy
