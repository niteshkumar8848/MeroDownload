import os
import sys

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MeroDownload")
    app_dir = os.path.dirname(os.path.abspath(__file__))
    window = MainWindow(app_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
