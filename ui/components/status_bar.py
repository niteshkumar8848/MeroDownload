from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


class BottomStatusBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.setObjectName("bottomStatusBar")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(14)

        self.active_lbl = QLabel("Active: 0")
        self.speed_lbl = QLabel("Speed: --")
        self.completed_lbl = QLabel("Completed (session): 0")
        self.queued_lbl = QLabel("Queued: 0")
        self.version_lbl = QLabel("yt-dlp: --")
        self.message_lbl = QLabel("")
        self.message_lbl.setObjectName("statusMessage")

        for w in [self.active_lbl, self.speed_lbl, self.completed_lbl, self.queued_lbl, self.version_lbl]:
            w.setObjectName("statusMetric")
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.message_lbl)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self.message_lbl.setText(""))

    def update_stats(self, stats: dict) -> None:
        self.active_lbl.setText(f"Active: {stats.get('active', 0)}")
        self.speed_lbl.setText(f"Speed: {stats.get('total_speed', '--')}")
        self.completed_lbl.setText(f"Completed (session): {stats.get('completed_session', 0)}")
        self.queued_lbl.setText(f"Queued: {stats.get('queued', 0)}")
        self.version_lbl.setText(f"yt-dlp: {stats.get('version', '--')}")

    def flash(self, message: str, timeout_ms: int = 4000) -> None:
        self.message_lbl.setText(message)
        self._flash_timer.start(timeout_ms)
