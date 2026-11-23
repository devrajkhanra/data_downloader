import os
import sys
from pathlib import Path

import PySide6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from market_data_downloader.ui_controller import DownloadController


def main() -> int:
    qt_dll_directory = None
    if sys.platform == "win32":
        qt_dll_directory = os.add_dll_directory(
            str(Path(PySide6.__file__).parent)
        )
    try:
        app = QGuiApplication(sys.argv)
        app.setApplicationName("Market Data Studio")
        QQuickStyle.setStyle("Basic")

        controller = DownloadController()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(
            QUrl.fromLocalFile(
                str(Path(__file__).parent / "ui" / "main.qml")
            )
        )
        if not engine.rootObjects():
            return 1
        return app.exec()
    finally:
        if qt_dll_directory is not None:
            qt_dll_directory.close()


if __name__ == "__main__":
    raise SystemExit(main())
