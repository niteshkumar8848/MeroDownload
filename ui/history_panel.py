import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils import format_bytes, truncated


class HistoryPanel(QWidget):
    refresh_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by title...")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Date", "Size", "Platform"])
        self.refresh_btn = QPushButton("Refresh")
        self.delete_btn = QPushButton("Delete Selected")

        top.addWidget(self.search, stretch=1)
        top.addWidget(self.sort_combo)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.delete_btn)
        root.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Thumbnail", "Title", "Platform", "Format", "Quality", "Size", "Date Downloaded", "File"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        root.addWidget(self.table)

        self.records: list[dict] = []
        self.search.textChanged.connect(self._emit_refresh)
        self.sort_combo.currentTextChanged.connect(self._emit_refresh)
        self.refresh_btn.clicked.connect(self._emit_refresh)
        self.delete_btn.clicked.connect(self._delete_selected)

    def set_records(self, records: list[dict]) -> None:
        self.records = records
        self.table.setRowCount(len(records))
        for row, rec in enumerate(records):
            date = rec.get("completed_at") or rec.get("added_at") or ""
            cells = [
                "Yes" if rec.get("thumbnail_url") else "-",
                truncated(rec.get("title") or "Untitled", 64),
                rec.get("platform") or "",
                (rec.get("format") or "").upper(),
                rec.get("quality") or "",
                format_bytes(rec.get("size_bytes") or 0),
                date,
                rec.get("filepath") or "",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                self.table.setItem(row, col, item)

    def _emit_refresh(self) -> None:
        self.refresh_requested.emit(self.search.text().strip(), self.sort_combo.currentText())

    def _delete_selected(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self.records):
            return
        record = self.records[idx]
        filepath = record.get("filepath") or ""
        delete_file = False
        if filepath and os.path.exists(filepath):
            resp = QMessageBox.question(
                self,
                "Delete file?",
                "Also delete the downloaded file from disk?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            delete_file = resp == QMessageBox.StandardButton.Yes
        self.delete_requested.emit(int(record["id"]), delete_file)
