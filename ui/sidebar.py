import shutil

from PyQt6.QtCore import pyqtSignal, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
)

from core.utils import format_bytes


ICON_SIZE = QSize(16, 16)


def create_icon(color_name: str, symbol: str = "") -> QIcon:
    """Create simple colored icon with optional symbol."""
    pixmap = QPixmap(ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Background circle/rect
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_name))
    painter.drawRoundedRect(2, 2, 12, 12, 6, 6)
    
    # Symbol/text
    if symbol:
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
    
    painter.end()
    return QIcon(pixmap)


class Sidebar(QFrame):
    nav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setMaximumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 16)
        root.setSpacing(12)

        title = QLabel("MeroDownload")
        title.setObjectName("appTitle")
        root.addWidget(title)

        subtitle = QLabel("Smart Media Downloader")
        subtitle.setObjectName("appSubtitle")
        root.addWidget(subtitle)

        self.buttons: dict[str, QPushButton] = {}
        nav_items = [
            ("Queue", create_icon("#238636", "Q"), "queue-active"),
            ("Completed", create_icon("#238636", "C"), "queue-completed"),
            ("Failed", create_icon("#f85149", "F"), "queue-failed"),
            ("Videos", create_icon("#2f81f7", "V"), "history-videos"),
            ("Audio", create_icon("#d16ba5", "A"), "history-audio"),
            ("Playlists", create_icon("#7ee787", "P"), "history-playlists"),
            ("Settings", create_icon("#8b949e", "S"), "settings"),
        ]
        for text, icon, _ in nav_items:
            b = QPushButton()
            b.setProperty("navButton", True)
            b.setIcon(icon)
            b.setIconSize(ICON_SIZE)
            b.setText(text)
            b.setCheckable(True)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda _, k=text: self._handle_nav(k))
            root.addWidget(b)
            self.buttons[text] = b

        root.addStretch(1)

        storage_section = QFrame()
        storage_section.setObjectName("storage-section")
        storage_layout = QVBoxLayout(storage_section)
        storage_layout.setContentsMargins(0, 0, 0, 0)
        storage_layout.setSpacing(6)

        meter_label = QLabel("Storage")
        meter_label.setObjectName("sidebarSectionLabel")
        storage_layout.addWidget(meter_label)

        self.storage_bar = QProgressBar()
        self.storage_bar.setRange(0, 100)
        self.storage_bar.setValue(0)
        self.storage_bar.setTextVisible(False)
        self.storage_bar.setFixedHeight(6)
        storage_layout.addWidget(self.storage_bar)

        self.storage_text = QLabel("0 GB of 0 GB")
        self.storage_text.setObjectName("sidebarStorageText")
        storage_layout.addWidget(self.storage_text)

        root.addWidget(storage_section)

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
            
            # Dynamic color based on usage
            if percent > 90:
                self.storage_bar.setStyleSheet("QProgressBar::chunk { background: #f85149; }")
            elif percent > 70:
                self.storage_bar.setStyleSheet("QProgressBar::chunk { background: #f0883e; }")
            else:
                self.storage_bar.setStyleSheet("QProgressBar::chunk { background: #238636; }")
        except Exception:
            self.storage_bar.setValue(0)
            self.storage_text.setText("N/A")
