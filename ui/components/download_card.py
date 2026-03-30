import os
import threading
import urllib.request

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from core.utils import truncated

PLATFORM_COLORS = {
    "YouTube": "#E24B4A",
    "Instagram": "#993556",
    "Twitter": "#185FA5",
    "TikTok": "#1a1a1a",
    "Facebook": "#185FA5",
    "Reddit": "#ff4500",
    "Other": "#6b7280",
}

ICON_SIZE = QSize(14, 14)


def create_icon(color_name: str, symbol: str = "") -> QIcon:
    pixmap = QPixmap(ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_name))
    painter.drawRoundedRect(2, 2, 10, 10, 5, 5)
    if symbol:
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)


class DownloadCard(QFrame):
    pause_clicked = pyqtSignal(int)
    resume_clicked = pyqtSignal(int)
    retry_clicked = pyqtSignal(int)
    remove_clicked = pyqtSignal(int)
    open_folder_clicked = pyqtSignal(int)
    thumbnail_loaded = pyqtSignal(bytes)

    def __init__(self, payload: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.payload = payload
        self.setObjectName("downloadCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(124)
        self.setMaximumHeight(190)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.thumb = QLabel("No preview")
        self.thumb.setObjectName("cardThumbnail")
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setMinimumSize(132, 74)
        self.thumb.setMaximumSize(132, 74)
        self.thumb.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        root.addWidget(self.thumb)

        center = QVBoxLayout()
        center.setSpacing(6)
        root.addLayout(center, stretch=1)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title = QLabel(truncated(payload.get("title") or "Untitled", 60))
        self.title.setObjectName("cardTitle")
        self.title.setWordWrap(True)
        self.badge = QLabel(payload.get("platform") or "Other")
        self.badge.setObjectName("badge")
        self.badge.setStyleSheet(self._badge_style(payload.get("platform") or "Other"))
        self.badge.setMinimumHeight(22)
        title_row.addWidget(self.title, 1)
        title_row.addWidget(self.badge)
        center.addLayout(title_row)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.meta = QLabel(self._meta_text(payload))
        self.meta.setObjectName("cardMeta")
        self.status = QLabel(payload.get("status", "QUEUED"))
        self.status.setObjectName("cardStatus")
        self.status.setMinimumHeight(24)
        meta_row.addWidget(self.meta, stretch=1)
        meta_row.addWidget(self.status)
        center.addLayout(meta_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(int(payload.get("progress", 0)))
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        center.addWidget(self.progress)

        speed_row = QHBoxLayout()
        self.speed = QLabel(f"Speed: {payload.get('speed', '--')}")
        self.eta = QLabel(f"ETA: {payload.get('eta', '--')}")
        self.speed.setObjectName("cardMeta")
        self.eta.setObjectName("cardMeta")
        speed_row.addWidget(self.speed)
        speed_row.addStretch(1)
        speed_row.addWidget(self.eta)
        center.addLayout(speed_row)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        root.addLayout(actions)

        self.pause_btn = QPushButton()
        self.pause_btn.setIcon(create_icon("#238636", "⏸"))
        self.pause_btn.setProperty("iconButton", True)
        self.pause_btn.setFixedSize(32, 30)
        self.open_btn = QPushButton()
        self.open_btn.setIcon(create_icon("#58a6ff", "📁"))
        self.open_btn.setProperty("iconButton", True)
        self.open_btn.setFixedSize(32, 30)
        self.remove_btn = QPushButton()
        self.remove_btn.setIcon(create_icon("#f85149", "🗑"))
        self.remove_btn.setProperty("iconButton", True)
        self.remove_btn.setFixedSize(32, 30)

        self.pause_btn.clicked.connect(self._toggle_pause_resume)
        self.open_btn.clicked.connect(lambda: self.open_folder_clicked.emit(self.payload["id"]))
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.payload["id"]))

        actions.addWidget(self.pause_btn)
        actions.addWidget(self.open_btn)
        actions.addStretch()
        actions.addWidget(self.remove_btn)

        self.thumbnail_loaded.connect(self._set_thumbnail)
        self._load_thumbnail(payload.get("thumbnail_url") or "")
        self._sync_buttons()
        self._update_button_texts()
        self._apply_status_style()

    def _update_button_texts(self):
        # Minimal text, icons primary
        self.pause_btn.setText("")
        self.open_btn.setText("")
        self.remove_btn.setText("")

    def update_payload(self, payload: dict) -> None:
        self.payload = payload
        self.title.setText(truncated(payload.get("title") or "Untitled", 60))
        platform = payload.get("platform") or "Other"
        self.badge.setText(platform)
        self.badge.setStyleSheet(self._badge_style(platform))
        self.meta.setText(self._meta_text(payload))
        self.status.setText(payload.get("status", "QUEUED"))
        self._apply_status_style()
        self.progress.setValue(int(payload.get("progress", 0)))
        self.speed.setText(f"Speed: {payload.get('speed', '--')}")
        self.eta.setText(f"ETA: {payload.get('eta', '--')}")
        if payload.get("thumbnail_url"):
            self._load_thumbnail(payload["thumbnail_url"])
        self._sync_buttons()

    def _meta_text(self, payload: dict) -> str:
        quality = payload.get("quality") or "-"
        fmt = (payload.get("format") or "-").upper()
        size = payload.get("size_text") or "--"
        return f"{fmt} • {quality} • {size}"

    def _toggle_pause_resume(self) -> None:
        status = self.payload.get("status")
        task_id = self.payload["id"]
        if status == "DOWNLOADING":
            self.pause_clicked.emit(task_id)
        elif status in {"PAUSED", "FAILED"}:
            self.resume_clicked.emit(task_id)

    def _sync_buttons(self) -> None:
        status = self.payload.get("status")
        self.pause_btn.setEnabled(status in {"DOWNLOADING", "PAUSED", "FAILED"})
        if status == "DOWNLOADING":
            self.pause_btn.setIcon(create_icon("#f85149", "⏸"))
            self.pause_btn.setToolTip("Pause download")
        elif status == "PAUSED":
            self.pause_btn.setIcon(create_icon("#238636", "▶"))
            self.pause_btn.setToolTip("Resume download")
        elif status == "FAILED":
            self.pause_btn.setIcon(create_icon("#f0883e", "↻"))
            self.pause_btn.setToolTip("Retry download")
        else:
            self.pause_btn.setIcon(create_icon("#8b949e", "•"))
            self.pause_btn.setToolTip("No action available")

        self.open_btn.setEnabled(bool(self.payload.get("filepath") and os.path.exists(self.payload["filepath"])))
        if self.open_btn.isEnabled():
            self.open_btn.setToolTip("Open folder")
        self.remove_btn.setToolTip("Remove task")

    def _apply_status_style(self) -> None:
        status = (self.payload.get("status") or "QUEUED").upper()
        color = {
            "QUEUED": "#8b949e",
            "DOWNLOADING": "#2f81f7",
            "PAUSED": "#e3a008",
            "FAILED": "#f85149",
            "COMPLETED": "#238636",
        }.get(status, "#8b949e")
        self.status.setStyleSheet(
            f"QLabel#cardStatus {{ background: {color}; color: white; border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600; }}"
        )

    def _badge_style(self, platform: str) -> str:
        color = PLATFORM_COLORS.get(platform, PLATFORM_COLORS["Other"])
        return f"QLabel#badge {{ background: {color}; color: white; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 500; }}"

    def _load_thumbnail(self, url: str) -> None:
        if not url:
            return

        def worker() -> None:
            try:
                with urllib.request.urlopen(url, timeout=6) as response:
                    self.thumbnail_loaded.emit(response.read())
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

    def _set_thumbnail(self, data: bytes) -> None:
        image = QImage()
        image.loadFromData(data)
        if image.isNull():
            return
        pix = QPixmap.fromImage(image)
        scaled_pix = pix.scaled(
            self.thumb.maximumSize(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.thumb.setPixmap(scaled_pix)
        self.thumb.setMinimumSize(scaled_pix.size())
