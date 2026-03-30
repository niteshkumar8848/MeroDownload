from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from yt_dlp.version import __version__ as ytdlp_version


class SettingsPanel(QWidget):
    save_requested = pyqtSignal(dict)
    theme_changed = pyqtSignal(str)

    def __init__(self, config: dict):
        super().__init__()
        root = QVBoxLayout(self)

        card = QFrame()
        form = QFormLayout(card)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.folder_input = QLineEdit(config.get("download_folder", ""))
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input, stretch=1)
        folder_row.addWidget(browse)
        wrapper = QWidget()
        wrapper.setLayout(folder_row)
        form.addRow("Default folder", wrapper)

        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 5)
        self.concurrent.setValue(int(config.get("max_concurrent", 2)))
        form.addRow("Max concurrent", self.concurrent)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mp3", "webm", "m4a"])
        self.format_combo.setCurrentText(config.get("default_format", "mp4"))
        form.addRow("Default format", self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "4K", "Best Available", "Audio Only"])
        self.quality_combo.setCurrentText(config.get("default_quality", "1080p"))
        form.addRow("Default quality", self.quality_combo)

        self.bandwidth = QSpinBox()
        self.bandwidth.setRange(0, 10_000_000)
        self.bandwidth.setSuffix(" KB/s (0 = unlimited)")
        self.bandwidth.setValue(int(config.get("bandwidth_limit", 0)))
        form.addRow("Bandwidth", self.bandwidth)

        self.proxy_input = QLineEdit(config.get("proxy", ""))
        form.addRow("Proxy", self.proxy_input)

        self.cookie_input = QLineEdit(config.get("cookie_file", ""))
        form.addRow("Cookie file", self.cookie_input)

        self.notify_chk = QCheckBox("Desktop notifications")
        self.notify_chk.setChecked(bool(config.get("notifications", True)))
        form.addRow("Notifications", self.notify_chk)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(config.get("theme", "light"))
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        form.addRow("Theme", self.theme_combo)

        self.embed_chk = QCheckBox("Auto-embed subtitles")
        self.embed_chk.setChecked(bool(config.get("embed_subtitles", False)))
        form.addRow("Subtitles", self.embed_chk)

        update_btn = QPushButton("Check yt-dlp update")
        update_btn.clicked.connect(self._show_ytdlp_version)
        form.addRow("yt-dlp", update_btn)

        root.addWidget(card)

        save_btn = QPushButton("Save settings")
        save_btn.clicked.connect(self._save)
        root.addWidget(save_btn)
        root.addStretch(1)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select download folder")
        if folder:
            self.folder_input.setText(folder)

    def _show_ytdlp_version(self) -> None:
        QMessageBox.information(self, "yt-dlp", f"Installed version: {ytdlp_version}\n\nRun: pip install -U yt-dlp")

    def _save(self) -> None:
        payload = {
            "download_folder": self.folder_input.text().strip(),
            "max_concurrent": int(self.concurrent.value()),
            "default_format": self.format_combo.currentText(),
            "default_quality": self.quality_combo.currentText(),
            "bandwidth_limit": int(self.bandwidth.value()),
            "proxy": self.proxy_input.text().strip(),
            "cookie_file": self.cookie_input.text().strip(),
            "notifications": self.notify_chk.isChecked(),
            "theme": self.theme_combo.currentText(),
            "embed_subtitles": self.embed_chk.isChecked(),
        }
        self.save_requested.emit(payload)
        QMessageBox.information(self, "Saved", "Settings saved successfully.")
