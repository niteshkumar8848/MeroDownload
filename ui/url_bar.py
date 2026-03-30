from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from core.utils import is_valid_url


class UrlBar(QFrame):
    add_requested = pyqtSignal(str, str, str, bool)

    def __init__(self, defaults: dict):
        super().__init__()
        self.setObjectName("urlBar")

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL (YouTube, Instagram, Twitter/X, Facebook, TikTok, Reddit)...")
        row.addWidget(self.url_input, stretch=1)

        self.paste_btn = QPushButton("Paste")
        self.paste_btn.clicked.connect(self._paste_clipboard)
        row.addWidget(self.paste_btn)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mp3", "webm", "m4a"])
        self.format_combo.setCurrentText(defaults.get("default_format", "mp4"))
        row.addWidget(self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "4K", "Best Available", "Audio Only"])
        self.quality_combo.setCurrentText(defaults.get("default_quality", "1080p"))
        row.addWidget(self.quality_combo)

        self.subtitle_chk = QCheckBox("Subtitles")
        self.subtitle_chk.setChecked(bool(defaults.get("embed_subtitles", False)))
        row.addWidget(self.subtitle_chk)

        self.add_btn = QPushButton("+ Add to Queue")
        self.add_btn.clicked.connect(self._add_to_queue)
        row.addWidget(self.add_btn)

    def _paste_clipboard(self) -> None:
        text = (QGuiApplication.clipboard().text() or "").strip()
        if text:
            self.url_input.setText(text)

    def _add_to_queue(self) -> None:
        url = self.url_input.text().strip()
        if not is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid video URL.")
            return
        self.add_requested.emit(
            url,
            self.format_combo.currentText(),
            self.quality_combo.currentText(),
            self.subtitle_chk.isChecked(),
        )
        self.url_input.clear()
