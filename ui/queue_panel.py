from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QWidget, QVBoxLayout

from ui.components.download_card import DownloadCard


class QueuePanel(QWidget):
    pause_requested = pyqtSignal(int)
    resume_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)
    open_folder_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.cards: dict[int, DownloadCard] = {}
        self.current_filter = "ACTIVE"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll)

        self.container = QWidget()
        self.inner = QVBoxLayout(self.container)
        self.inner.setContentsMargins(16, 16, 16, 16)
        self.inner.setSpacing(12)
        self.scroll.setWidget(self.container)

        self.empty_hint = QLabel("No downloads in this view yet")
        self.empty_hint.setObjectName("queueEmptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setMinimumHeight(240)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_cards()

    def _get_column_count(self) -> int:
        return 1

    def _reflow_cards(self):
        visible_cards = [card for card in self.cards.values() if card.isVisible()]
        visible_cards.sort(key=lambda c: int(c.payload.get("id", 0)), reverse=True)

        # Clear list layout
        while self.inner.count():
            child = self.inner.takeAt(0)
            # Keep widgets parented to container; only detach from layout.
            # Detaching parent here can turn child widgets into top-level windows.
            _ = child.widget()

        if not visible_cards:
            self.inner.addWidget(self.empty_hint)
            self.inner.addStretch(1)
            return

        for card in visible_cards:
            self.inner.addWidget(card)
        self.inner.addStretch(1)

    def add_or_update(self, payload: dict) -> None:
        task_id = payload["id"]
        card = self.cards.get(task_id)
        if card is None:
            card = DownloadCard(payload)
            card.pause_clicked.connect(self.pause_requested)
            card.resume_clicked.connect(self.resume_requested)
            card.remove_clicked.connect(self.remove_requested)
            card.open_folder_clicked.connect(self.open_folder_requested)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.cards[task_id] = card
        else:
            card.update_payload(payload)
        
        self._reflow_cards()

    def remove_card(self, task_id: int) -> None:
        card = self.cards.pop(task_id, None)
        if not card:
            return
        card.setParent(None)
        card.deleteLater()
        self._reflow_cards()

    def set_filter(self, status_filter: str) -> None:
        self.current_filter = status_filter
        for card in self.cards.values():
            status = card.payload.get("status", "")
            visible = True
            if status_filter == "COMPLETED":
                visible = status == "COMPLETED"
            elif status_filter == "FAILED":
                visible = status == "FAILED"
            elif status_filter == "ACTIVE":
                visible = status in ["DOWNLOADING", "PAUSED", "QUEUED"]
            card.setVisible(visible)
            if visible:
                card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            else:
                card.hide()
        self._reflow_cards()
