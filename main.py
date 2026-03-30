import os
import sys

from PyQt6.QtCore import QLockFile, QStandardPaths
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


_APP_LOCK: QLockFile | None = None


def _acquire_single_instance_lock() -> bool:
    global _APP_LOCK  # noqa: PLW0603
    lock_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation) or "/tmp"
    lock_path = os.path.join(lock_dir, "merodownload.lock")
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        return False
    _APP_LOCK = lock
    return True


def main() -> int:
    if not _acquire_single_instance_lock():
        print("MeroDownload is already running.")
        return 0

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("MeroDownload")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    window = MainWindow(app_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
