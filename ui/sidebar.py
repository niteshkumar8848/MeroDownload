import shutil

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from core.utils import format_bytes


class Sidebar(QFrame):
    nav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(200)
        self.setObjectName("sidebar")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("MeroDownload")
        title.setStyleSheet("font-size: 15px; font-weight: 500;")
        root.addWidget(title)

        self.buttons: dict[str, QPushButton] = {}
        for key in ["Queue", "Completed", "Failed", "Videos", "Audio", "Playlists", "Settings"]:
            b = QPushButton(key)
            b.setCheckable(True)
            b.clicked.connect(lambda _, k=key: self._handle_nav(k))
            root.addWidget(b)
            self.buttons[key] = b

        root.addStretch(1)

        meter_label = QLabel("Storage")
        meter_label.setStyleSheet("font-size: 11px; color: #666;")
        root.addWidget(meter_label)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)
        self.storage_bar.setTextVisible(False)
        root.addWidget(self.storage_bar)

        self.storage_text = QLabel("0 GB of 0 GB")
        self.storage_text.setStyleSheet("font-size: 11px; color: #666;")
        root.addWidget(self.storage_text)

        self._handle_nav("Queue")

    def _handle_nav(self, key: str) -> None:
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
        self.nav_clicked.emit(key)

    def update_storage(self, folder: str) -> None:
        try:
            usage = shutil.disk_usage(folder)
            used = usage.used
            total = usage.total
            percent = int((used / total) * 100) if total else 0
            self.storage_bar.setValue(percent)
            self.storage_text.setText(f"{format_bytes(used)} of {format_bytes(total)}")
        except Exception:
            self.storage_bar.setValue(0)
            self.storage_text.setText("N/A")
