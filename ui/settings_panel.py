from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from yt_dlp.version import __version__ as ytdlp_version


ICON_SIZE = QSize(16, 16)


def create_icon(color_name: str, symbol: str = "") -> QIcon:
    pixmap = QPixmap(ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_name))
    painter.drawRoundedRect(3, 3, 10, 10, 5, 5)
    if symbol:
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)


def create_section(title: str, icon_color: str, icon_symbol: str = "") -> tuple[QFrame, QFormLayout]:
    section = QFrame()
    section.setObjectName("settingsSection")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    header = QHBoxLayout()
    icon_label = QLabel()
    icon_label.setPixmap(create_icon(icon_color, icon_symbol).pixmap(ICON_SIZE))
    title_label = QLabel(title)
    title_label.setObjectName("settingsSectionTitle")
    header.addWidget(icon_label)
    header.addWidget(title_label)
    header.addStretch(1)
    layout.addLayout(header)

    form = QFormLayout()
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addLayout(form)

    return section, form


class SettingsPanel(QWidget):
    save_requested = pyqtSignal(dict)

    def __init__(self, config: dict):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(14)

        dl_section, dl_form = create_section("Download", "#238636", "D")
        self.folder_input = QLineEdit(config.get("download_folder", ""))
        browse = QPushButton("Browse")
        browse.setProperty("secondary", True)
        browse.setIcon(create_icon("#2f81f7", "B"))
        browse.clicked.connect(self._browse_folder)
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(browse)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_row)
        dl_form.addRow("Folder:", folder_widget)

        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 8)
        self.concurrent.setValue(int(config.get("max_concurrent", 2)))
        dl_form.addRow("Concurrent:", self.concurrent)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mp3", "webm", "m4a"])
        self.format_combo.setCurrentText(config.get("default_format", "mp4"))
        dl_form.addRow("Default format:", self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "4K", "Best Available", "Audio Only"])
        self.quality_combo.setCurrentText(config.get("default_quality", "1080p"))
        dl_form.addRow("Default quality:", self.quality_combo)
        root.addWidget(dl_section)

        adv_section, adv_form = create_section("Advanced", "#9e6bff", "A")
        self.bandwidth = QSpinBox()
        self.bandwidth.setRange(0, 50_000_000)
        self.bandwidth.setSuffix(" KB/s (0 = unlimited)")
        self.bandwidth.setValue(int(config.get("bandwidth_limit", 0)))
        adv_form.addRow("Bandwidth:", self.bandwidth)

        self.proxy_input = QLineEdit(config.get("proxy", ""))
        adv_form.addRow("Proxy URL:", self.proxy_input)

        self.cookie_input = QLineEdit(config.get("cookie_file", ""))
        adv_form.addRow("Cookie file:", self.cookie_input)
        root.addWidget(adv_section)

        app_section, app_form = create_section("Appearance", "#e3a008", "T")
        self.notify_chk = QCheckBox("Desktop notifications")
        self.notify_chk.setChecked(bool(config.get("notifications", True)))
        app_form.addRow("", self.notify_chk)

        self.embed_chk = QCheckBox("Embed subtitles")
        self.embed_chk.setChecked(bool(config.get("embed_subtitles", False)))
        app_form.addRow("", self.embed_chk)
        root.addWidget(app_section)

        info_section, info_form = create_section("yt-dlp", "#f0883e", "Y")
        version_label = QLabel(f"Installed version: {ytdlp_version}")
        update_btn = QPushButton("Update Command")
        update_btn.setProperty("secondary", True)
        update_btn.clicked.connect(self._show_ytdlp_version)
        info_form.addRow("Version:", version_label)
        info_form.addRow("Update:", update_btn)
        root.addWidget(info_section)

        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("primary", True)
        save_btn.setIcon(create_icon("#238636", "S"))
        save_btn.clicked.connect(self._save)
        save_btn.setMinimumHeight(40)
        root.addWidget(save_btn)

        self.inline_message = QLabel("")
        self.inline_message.setObjectName("settingsInlineMessage")
        root.addWidget(self.inline_message)

        root.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select download folder")
        if folder:
            self.folder_input.setText(folder)

    def _show_ytdlp_version(self) -> None:
        QGuiApplication.clipboard().setText("pip install -U yt-dlp")
        self.inline_message.setText(f"yt-dlp {ytdlp_version} | Update command copied to clipboard")

    def _save(self) -> None:
        payload = {
            "download_folder": self.folder_input.text().strip(),
            "max_concurrent": self.concurrent.value(),
            "default_format": self.format_combo.currentText(),
            "default_quality": self.quality_combo.currentText(),
            "bandwidth_limit": self.bandwidth.value(),
            "proxy": self.proxy_input.text().strip(),
            "cookie_file": self.cookie_input.text().strip(),
            "notifications": self.notify_chk.isChecked(),
            "theme": "dark",
            "embed_subtitles": self.embed_chk.isChecked(),
        }
        self.save_requested.emit(payload)
        self.inline_message.setText("Settings updated successfully.")
