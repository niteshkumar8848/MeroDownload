import os
import threading
import urllib.request

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
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
        self.setStyleSheet("QFrame#downloadCard { border: 1px solid rgba(0,0,0,0.15); border-radius: 8px; }")

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.thumb = QLabel("No preview")
        self.thumb.setFixedSize(120, 68)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setStyleSheet("background: #f0f0f0; border-radius: 6px; color: #808080;")
        root.addWidget(self.thumb)

        center = QVBoxLayout()
        center.setSpacing(5)
        root.addLayout(center, stretch=1)

        title_row = QHBoxLayout()
        self.title = QLabel(truncated(payload.get("title") or "Untitled", 70))
        self.title.setStyleSheet("font-size: 13px; font-weight: 500;")
        self.badge = QLabel(payload.get("platform") or "Other")
        self.badge.setStyleSheet(self._badge_style(payload.get("platform") or "Other"))
        title_row.addWidget(self.title, stretch=1)
        title_row.addWidget(self.badge)
        center.addLayout(title_row)

        meta_row = QHBoxLayout()
        self.meta = QLabel(self._meta_text(payload))
        self.meta.setStyleSheet("font-size: 11px; color: #555;")
        meta_row.addWidget(self.meta)
        meta_row.addStretch(1)
        self.status = QLabel(payload.get("status", "QUEUED"))
        self.status.setStyleSheet("font-size: 11px; color: #333; font-weight: 500;")
        meta_row.addWidget(self.status)
        center.addLayout(meta_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(int(payload.get("progress", 0)))
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        center.addWidget(self.progress)

        speed_eta = QHBoxLayout()
        self.speed = QLabel(f"Speed: {payload.get('speed', '--')}")
        self.eta = QLabel(f"ETA: {payload.get('eta', '--')}")
        self.speed.setStyleSheet("font-size: 11px; color: #555;")
        self.eta.setStyleSheet("font-size: 11px; color: #555;")
        speed_eta.addWidget(self.speed)
        speed_eta.addWidget(self.eta)
        speed_eta.addStretch(1)
        center.addLayout(speed_eta)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        root.addLayout(actions)

        self.pause_btn = QPushButton("Pause")
        self.open_btn = QPushButton("Open")
        self.remove_btn = QPushButton("Remove")
        self.pause_btn.clicked.connect(self._toggle_pause_resume)
        self.open_btn.clicked.connect(lambda: self.open_folder_clicked.emit(self.payload["id"]))
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.payload["id"]))

        actions.addWidget(self.pause_btn)
        actions.addWidget(self.open_btn)
        actions.addWidget(self.remove_btn)

        self.thumbnail_loaded.connect(self._set_thumbnail)
        self._load_thumbnail(payload.get("thumbnail_url") or "")
        self._sync_buttons()

    def update_payload(self, payload: dict) -> None:
        self.payload = payload
        self.title.setText(truncated(payload.get("title") or "Untitled", 70))
        platform = payload.get("platform") or "Other"
        self.badge.setText(platform)
        self.badge.setStyleSheet(self._badge_style(platform))
        self.meta.setText(self._meta_text(payload))
        self.status.setText(payload.get("status", "QUEUED"))
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
        if status == "DOWNLOADING":
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(True)
        elif status in {"PAUSED", "FAILED"}:
            self.pause_btn.setText("Resume" if status == "PAUSED" else "Retry")
            self.pause_btn.setEnabled(True)
        else:
            self.pause_btn.setText("Pause")
            self.pause_btn.setEnabled(False)
        self.open_btn.setEnabled(bool(self.payload.get("filepath") and os.path.exists(self.payload["filepath"])))

    def _badge_style(self, platform: str) -> str:
        color = PLATFORM_COLORS.get(platform, PLATFORM_COLORS["Other"])
        return (
            f"background: {color}; color: white; border-radius: 10px; "
            "padding: 2px 8px; font-size: 11px;"
        )

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
        pix = QPixmap.fromImage(image).scaled(
            self.thumb.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumb.setPixmap(pix)
