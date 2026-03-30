from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


class BottomStatusBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(36)
        self.setObjectName("bottomStatusBar")
        self.setStyleSheet("QFrame#bottomStatusBar { border-top: 1px solid rgba(0,0,0,0.15); }")

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)

        self.active_lbl = QLabel("Active: 0")
        self.speed_lbl = QLabel("Speed: --")
        self.completed_lbl = QLabel("Completed (session): 0")
        self.queued_lbl = QLabel("Queued: 0")
        self.version_lbl = QLabel("yt-dlp: --")

        for w in [self.active_lbl, self.speed_lbl, self.completed_lbl, self.queued_lbl, self.version_lbl]:
            row.addWidget(w)
        row.addStretch(1)

    def update_stats(self, stats: dict) -> None:
        self.active_lbl.setText(f"Active: {stats.get('active', 0)}")
        self.speed_lbl.setText(f"Speed: {stats.get('total_speed', '--')}")
        self.completed_lbl.setText(f"Completed (session): {stats.get('completed_session', 0)}")
        self.queued_lbl.setText(f"Queued: {stats.get('queued', 0)}")
        self.version_lbl.setText(f"yt-dlp: {stats.get('version', '--')}")
