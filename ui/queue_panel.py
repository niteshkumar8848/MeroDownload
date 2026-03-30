from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ui.components.download_card import DownloadCard


class QueuePanel(QWidget):
    pause_requested = pyqtSignal(int)
    resume_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)
    open_folder_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.cards: dict[int, DownloadCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        root.addWidget(self.scroll)

        self.container = QWidget()
        self.inner = QVBoxLayout(self.container)
        self.inner.setContentsMargins(8, 8, 8, 8)
        self.inner.setSpacing(8)
        self.inner.addStretch(1)
        self.scroll.setWidget(self.container)

    def add_or_update(self, payload: dict) -> None:
        task_id = payload["id"]
        card = self.cards.get(task_id)
        if card is None:
            card = DownloadCard(payload)
            card.pause_clicked.connect(self.pause_requested)
            card.resume_clicked.connect(self.resume_requested)
            card.remove_clicked.connect(self.remove_requested)
            card.open_folder_clicked.connect(self.open_folder_requested)
            self.cards[task_id] = card
            self.inner.insertWidget(0, card)
        else:
            card.update_payload(payload)

    def remove_card(self, task_id: int) -> None:
        card = self.cards.pop(task_id, None)
        if not card:
            return
        card.setParent(None)
        card.deleteLater()

    def set_filter(self, status_filter: str) -> None:
        for card in self.cards.values():
            status = card.payload.get("status")
            visible = True
            if status_filter == "COMPLETED":
                visible = status == "COMPLETED"
            elif status_filter == "FAILED":
                visible = status == "FAILED"
            elif status_filter == "ACTIVE":
                visible = status != "COMPLETED"
            card.setVisible(visible)
