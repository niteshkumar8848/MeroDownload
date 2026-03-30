import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
    open_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._compact = False
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        toolbar = QFrame()
        toolbar.setObjectName("historyToolbar")
        top = QHBoxLayout(toolbar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by title...")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Date", "Size", "Platform"])
        self.open_btn = QPushButton("Open Selected")
        self.open_btn.setProperty("secondary", True)
        self.refresh_btn = QPushButton("Refresh")
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setProperty("danger", True)

        top.addWidget(self.search, stretch=1)
        top.addWidget(self.sort_combo)
        top.addWidget(self.open_btn)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.delete_btn)
        root.addWidget(toolbar)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(
            ["Preview", "Title", "Platform", "Format", "Quality", "Size", "Downloaded", "File"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)
        root.addWidget(self.table)

        self.summary_lbl = QLabel("No files yet")
        self.summary_lbl.setObjectName("historySummary")
        root.addWidget(self.summary_lbl)

        self.records: list[dict] = []
        self.search.textChanged.connect(self._emit_refresh)
        self.sort_combo.currentTextChanged.connect(self._emit_refresh)
        self.open_btn.clicked.connect(self._open_selected)
        self.refresh_btn.clicked.connect(self._emit_refresh)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.table.itemDoubleClicked.connect(lambda _: self._open_selected())
        self._apply_layout(force=True)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply_layout()

    def _apply_layout(self, force: bool = False) -> None:
        compact = self.width() < 1100
        if not force and compact == self._compact:
            return
        self._compact = compact
        self.table.setColumnHidden(7, compact)
        self.table.setColumnHidden(4, compact)

    def set_records(self, records: list[dict]) -> None:
        self.records = records
        self.table.setRowCount(len(records))
        self.summary_lbl.setText(f"Showing {len(records)} file(s)")
        self.open_btn.setEnabled(bool(records))
        self.delete_btn.setEnabled(bool(records))

        for row, rec in enumerate(records):
            date = rec.get("completed_at") or rec.get("added_at") or ""
            filepath = rec.get("filepath") or ""
            filename = os.path.basename(filepath) if filepath else "-"
            cells = [
                "●" if rec.get("thumbnail_url") else "•",
                truncated(rec.get("title") or "Untitled", 72),
                rec.get("platform") or "",
                (rec.get("format") or "").upper(),
                rec.get("quality") or "",
                format_bytes(rec.get("size_bytes") or 0),
                date,
                truncated(filename, 48),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                if col in {0, 2, 3, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 1:
                    item.setToolTip(rec.get("title") or "Untitled")
                if col == 7 and filepath:
                    item.setToolTip(filepath)
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 34)

    def _emit_refresh(self) -> None:
        self.refresh_requested.emit(self.search.text().strip(), self.sort_combo.currentText())

    def _open_selected(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self.records):
            return
        filepath = self.records[idx].get("filepath") or ""
        if filepath:
            self.open_requested.emit(filepath)

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
