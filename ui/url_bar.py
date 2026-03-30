from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QLineEdit,
    QPushButton,
)

from core.utils import is_valid_url


class UrlBar(QFrame):
    add_requested = pyqtSignal(str, str, str, bool)

    def __init__(self, defaults: dict):
        super().__init__()
        self.setObjectName("urlBar")
        self._compact = False

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(14, 12, 14, 12)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("Paste a video URL (YouTube, Instagram, X, Facebook, TikTok, Reddit...)")
        self.url_input.returnPressed.connect(self._add_to_queue)
        self.url_input.textChanged.connect(lambda: self.url_input.setStyleSheet(""))

        self.paste_btn = QPushButton("Paste")
        self.paste_btn.setProperty("secondary", True)
        self.paste_btn.clicked.connect(self._paste_clipboard)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mp3", "webm", "m4a"])
        self.format_combo.setCurrentText(defaults.get("default_format", "mp4"))
        self.format_combo.setMinimumWidth(90)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "4K", "Best Available", "Audio Only"])
        self.quality_combo.setCurrentText(defaults.get("default_quality", "1080p"))
        self.quality_combo.setMinimumWidth(130)

        self.subtitle_chk = QCheckBox("Subtitles")
        self.subtitle_chk.setChecked(bool(defaults.get("embed_subtitles", False)))

        self.add_btn = QPushButton("Add To Queue")
        self.add_btn.setProperty("primary", True)
        self.add_btn.clicked.connect(self._add_to_queue)
        self._apply_layout(force=True)

    def set_busy(self, busy: bool) -> None:
        self.url_input.setEnabled(not busy)
        self.paste_btn.setEnabled(not busy)
        self.format_combo.setEnabled(not busy)
        self.quality_combo.setEnabled(not busy)
        self.subtitle_chk.setEnabled(not busy)
        self.add_btn.setEnabled(not busy)
        self.add_btn.setText("Checking..." if busy else "Add To Queue")

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply_layout()

    def _clear_layout(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                self.grid.removeWidget(widget)

    def _apply_layout(self, force: bool = False) -> None:
        compact = self.width() < 1100
        if not force and compact == self._compact:
            return
        self._compact = compact
        self._clear_layout()

        for col in range(6):
            self.grid.setColumnStretch(col, 0)

        if compact:
            self.grid.addWidget(self.url_input, 0, 0, 1, 4)
            self.grid.addWidget(self.paste_btn, 0, 4)
            self.grid.addWidget(self.format_combo, 1, 0)
            self.grid.addWidget(self.quality_combo, 1, 1)
            self.grid.addWidget(self.subtitle_chk, 1, 2)
            self.grid.addWidget(self.add_btn, 1, 3, 1, 2)
            self.grid.setColumnStretch(3, 1)
        else:
            self.grid.addWidget(self.url_input, 0, 0)
            self.grid.addWidget(self.paste_btn, 0, 1)
            self.grid.addWidget(self.format_combo, 0, 2)
            self.grid.addWidget(self.quality_combo, 0, 3)
            self.grid.addWidget(self.subtitle_chk, 0, 4)
            self.grid.addWidget(self.add_btn, 0, 5)
            self.grid.setColumnStretch(0, 1)

    def _paste_clipboard(self) -> None:
        text = (QGuiApplication.clipboard().text() or "").strip()
        if text:
            self.url_input.setText(text)

    def _add_to_queue(self) -> None:
        url = self.url_input.text().strip()
        if not is_valid_url(url):
            self.url_input.setStyleSheet("border: 1px solid #f85149;")
            self.url_input.setFocus()
            return
        self.add_requested.emit(
            url,
            self.format_combo.currentText(),
            self.quality_combo.currentText(),
            self.subtitle_chk.isChecked(),
        )
        self.url_input.clear()
